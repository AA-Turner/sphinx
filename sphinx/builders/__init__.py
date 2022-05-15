"""Builder superclass for all builders."""

import codecs
import pickle
import time
import types
import warnings
from os import path
from typing import (TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple,
                    Type, Union)

from docutils import nodes
from docutils.nodes import Node

from sphinx.config import Config
from sphinx.deprecation import RemovedInSphinx70Warning
from sphinx.environment import CONFIG_CHANGED_REASON, CONFIG_OK, BuildEnvironment
from sphinx.environment.adapters.asset import ImageAdapter
from sphinx.errors import SphinxError
from sphinx.events import EventManager
from sphinx.locale import __
from sphinx.util import (UnicodeDecodeErrorHandler, get_filetype, import_object, logging,
                         progress_message, rst, status_iterator)
from sphinx.util.build_phase import BuildPhase
from sphinx.util.console import bold  # type: ignore
from sphinx.util.docutils import sphinx_domains
from sphinx.util.i18n import CatalogInfo, CatalogRepository, docname_to_domain
from sphinx.util.osutil import SEP, ensuredir, relative_uri, relpath
from sphinx.util import parallel
from sphinx.util.tags import Tags

# side effect: registers roles and directives
from sphinx import directives  # NOQA isort:skip
from sphinx import roles  # NOQA isort:skip
try:
    import multiprocessing
except ImportError:
    multiprocessing = None

if TYPE_CHECKING:
    from sphinx.application import Sphinx


logger = logging.getLogger(__name__)


class Builder:
    """
    Builds target formats from the reST sources.
    """

    #: The builder's name, for the -b command line option.
    name = ''
    #: The builder's output format, or '' if no document output is produced.
    format = ''
    #: The message emitted upon successful build completion. This can be a
    #: printf-style template string with the following keys: ``outdir``,
    #: ``project``
    epilog = ''

    #: default translator class for the builder.  This can be overridden by
    #: :py:meth:`app.set_translator()`.
    default_translator_class: Type[nodes.NodeVisitor] = None
    # doctree versioning method
    versioning_method = 'none'
    versioning_compare = False
    #: allow parallel write_doc() calls
    allow_parallel = True
    # support translation
    use_message_catalog = True

    #: The list of MIME types of image formats supported by the builder.
    #: Image files are searched in the order in which they appear here.
    supported_image_types: List[str] = []
    #: The builder supports remote images or not.
    supported_remote_images = False
    #: The builder supports data URIs or not.
    supported_data_uri_images = False

    def __init__(self, app: "Sphinx") -> None:
        self.srcdir = app.srcdir
        self.confdir = app.confdir
        self.outdir = app.outdir
        self.doctreedir = app.doctreedir
        ensuredir(self.doctreedir)

        self.app: Sphinx = app
        self.env: Optional[BuildEnvironment] = None
        self.events: EventManager = app.events
        self.config: Config = app.config
        self.tags: Tags = app.tags
        self.tags.add(self.format)
        self.tags.add(self.name)
        self.tags.add("format_%s" % self.format)
        self.tags.add("builder_%s" % self.name)

        # images that need to be copied over (source -> dest)
        self.images: Dict[str, str] = {}
        # basename of images directory
        self.imagedir = ""
        # relative path to image directory from current docname (used at writing docs)
        self.imgpath = ""

        # these get set later
        self.parallel_ok = False
        self.finish_tasks: Any = None

    def set_environment(self, env: BuildEnvironment) -> None:
        """Store BuildEnvironment object."""
        self.env = env
        self.env.set_versioning_method(self.versioning_method,
                                       self.versioning_compare)

    def get_translator_class(self, *args: Any) -> Type[nodes.NodeVisitor]:
        """Return a class of translator."""
        return self.app.registry.get_translator_class(self)

    def create_translator(self, *args: Any) -> nodes.NodeVisitor:
        """Return an instance of translator.

        This method returns an instance of ``default_translator_class`` by default.
        Users can replace the translator class with ``app.set_translator()`` API.
        """
        return self.app.registry.create_translator(self, *args)

    # helper methods
    def init(self) -> None:
        """Load necessary templates and perform initialization.  The default
        implementation does nothing.
        """
        pass

    def create_template_bridge(self) -> None:
        """Return the template bridge configured."""
        if self.config.template_bridge:
            self.templates = import_object(self.config.template_bridge,
                                           'template_bridge setting')()
        else:
            from sphinx.jinja2glue import BuiltinTemplateLoader
            self.templates = BuiltinTemplateLoader()

    def get_target_uri(self, docname: str, typ: str = None) -> str:
        """Return the target URI for a document name.

        *typ* can be used to qualify the link characteristic for individual
        builders.
        """
        raise NotImplementedError

    def get_relative_uri(self, from_: str, to: str, typ: str = None) -> str:
        """Return a relative URI between two source filenames.

        May raise environment.NoUri if there's no way to return a sensible URI.
        """
        return relative_uri(self.get_target_uri(from_),
                            self.get_target_uri(to, typ))

    def get_outdated_docs(self) -> Union[str, Iterable[str]]:
        """Return an iterable of output files that are outdated, or a string
        describing what an update build will build.

        If the builder does not output individual files corresponding to
        source files, return a string here.  If it does, return an iterable
        of those files that need to be written.
        """
        raise NotImplementedError

    def get_asset_paths(self) -> List[str]:
        """Return list of paths for assets (ex. templates, CSS, etc.)."""
        return []

    def post_process_images(self, doctree: Node) -> None:
        """Pick the best candidate for all image URIs."""
        images = ImageAdapter(self.env)
        for node in doctree.findall(nodes.image):
            if '?' in node['candidates']:
                # don't rewrite nonlocal image URIs
                continue
            if '*' not in node['candidates']:
                for imgtype in self.supported_image_types:
                    candidate = node['candidates'].get(imgtype, None)
                    if candidate:
                        break
                else:
                    mimetypes = sorted(node['candidates'])
                    image_uri = images.get_original_image_uri(node['uri'])
                    if mimetypes:
                        logger.warning(__('a suitable image for %s builder not found: '
                                          '%s (%s)'),
                                       self.name, mimetypes, image_uri, location=node)
                    else:
                        logger.warning(__('a suitable image for %s builder not found: %s'),
                                       self.name, image_uri, location=node)
                    continue
                node['uri'] = candidate
            else:
                candidate = node['uri']
            if candidate not in self.env.images:
                # non-existing URI; let it alone
                continue
            self.images[candidate] = self.env.images[candidate][1]

    # compile po methods

    def compile_catalogs(self, catalogs: Set[CatalogInfo], message: str) -> None:
        if not self.config.gettext_auto_build:
            return

        def cat2relpath(cat: CatalogInfo) -> str:
            return relpath(cat.mo_path, self.env.srcdir).replace(path.sep, SEP)

        logger.info(bold(__('building [mo]: ')) + message)
        for catalog in status_iterator(catalogs, __('writing output... '), "darkgreen",
                                       len(catalogs), self.app.verbosity,
                                       stringify_func=cat2relpath):
            catalog.write_mo(self.config.language,
                             self.config.gettext_allow_fuzzy_translations)

    def compile_all_catalogs(self) -> None:
        repo = CatalogRepository(self.srcdir, self.config.locale_dirs,
                                 self.config.language, self.config.source_encoding)
        message = __('all of %d po files') % len(list(repo.catalogs))
        self.compile_catalogs(set(repo.catalogs), message)

    def compile_specific_catalogs(self, specified_files: List[str]) -> None:
        def to_domain(fpath: str) -> Optional[str]:
            docname = self.env.path2doc(path.abspath(fpath))
            if docname:
                return docname_to_domain(docname, self.config.gettext_compact)
            else:
                return None

        catalogs = set()
        domains = set(map(to_domain, specified_files))
        repo = CatalogRepository(self.srcdir, self.config.locale_dirs,
                                 self.config.language, self.config.source_encoding)
        for catalog in repo.catalogs:
            if catalog.domain in domains and catalog.is_outdated():
                catalogs.add(catalog)
        message = __('targets for %d po files that are specified') % len(catalogs)
        self.compile_catalogs(catalogs, message)

    def compile_update_catalogs(self) -> None:
        repo = CatalogRepository(self.srcdir, self.config.locale_dirs,
                                 self.config.language, self.config.source_encoding)
        catalogs = {c for c in repo.catalogs if c.is_outdated()}
        message = __('targets for %d po files that are out of date') % len(catalogs)
        self.compile_catalogs(catalogs, message)

    # build methods

    def build_all(self) -> None:
        """Build all source files."""
        self.build(None, summary=__('all source files'), method='all')

    def build_specific(self, filenames: List[str]) -> None:
        """Only rebuild as much as needed for changes in the *filenames*."""
        # bring the filenames to the canonical format, that is,
        # relative to the source directory and without source_suffix.
        dirlen = len(self.srcdir) + 1
        to_write = []
        suffixes: Tuple[str] = tuple(self.config.source_suffix)  # type: ignore
        for filename in filenames:
            filename = path.normpath(path.abspath(filename))
            if not filename.startswith(self.srcdir):
                logger.warning(__('file %r given on command line is not under the '
                                  'source directory, ignoring'), filename)
                continue
            if not path.isfile(filename):
                logger.warning(__('file %r given on command line does not exist, '
                                  'ignoring'), filename)
                continue
            filename = filename[dirlen:]
            for suffix in suffixes:
                if filename.endswith(suffix):
                    filename = filename[:-len(suffix)]
                    break
            filename = filename.replace(path.sep, SEP)
            to_write.append(filename)
        self.build(to_write, method='specific',
                   summary=__('%d source files given on command line') % len(to_write))

    def build_update(self) -> None:
        """Only rebuild what was changed or added since last build."""
        to_build = self.get_outdated_docs()
        if isinstance(to_build, str):
            self.build(['__all__'], to_build)
        else:
            to_build = list(to_build)
            self.build(to_build,
                       summary=__('targets for %d source files that are out of date') %
                       len(to_build))

    def build(self, docnames: Iterable[str], summary: str = None, method: str = 'update') -> None:  # NOQA
        """Main build method.

        First updates the environment, and then calls :meth:`write`.
        """
        if summary:
            logger.info(bold(__('building [%s]: ') % self.name) + summary)

        # while reading, collect all warnings from docutils
        with logging.pending_warnings():
            updated_docnames = set(self.read())

        doccount = len(updated_docnames)
        logger.info(bold(__('looking for now-outdated files... ')), nonl=True)
        for docname in self.env.check_dependents(self.app, updated_docnames):
            updated_docnames.add(docname)
        outdated = len(updated_docnames) - doccount
        if outdated:
            logger.info(__('%d found'), outdated)
        else:
            logger.info(__('none found'))

        if updated_docnames:
            # save the environment
            from sphinx.application import ENV_PICKLE_FILENAME
            with progress_message(__('pickling environment')):
                with open(path.join(self.doctreedir, ENV_PICKLE_FILENAME), 'wb') as f:
                    pickle.dump(self.env, f, pickle.HIGHEST_PROTOCOL)

            # global actions
            self.app.phase = BuildPhase.CONSISTENCY_CHECK
            with progress_message(__('checking consistency')):
                self.env.check_consistency()
        else:
            if method == 'update' and not docnames:
                logger.info(bold(__('no targets are out of date.')))
                return

        self.app.phase = BuildPhase.RESOLVING

        # filter "docnames" (list of outdated files) by the updated
        # found_docs of the environment; this will remove docs that
        # have since been removed
        if docnames and docnames != ['__all__']:
            docnames = set(docnames) & self.env.found_docs

        # determine if we can write in parallel
        self.parallel_ok = self.app.parallel > 1 and self.app.is_parallel_allowed('write')

        #  create a task executor to use for misc. "finish-up" tasks
        # if self.parallel_ok:
        #     self.finish_tasks = ParallelTasks(self.app.parallel)
        # else:
        # for now, just execute them serially
        self.finish_tasks = parallel.SerialTasks()

        # write all "normal" documents (or everything for some builders)
        self.write(docnames, list(updated_docnames), method)

        # finish (write static files etc.)
        self.finish()

        # wait for all tasks
        self.finish_tasks.join()

    def read(self) -> List[str]:
        """(Re-)read all files new or changed since last update.

        Store all environment docnames in the canonical format (ie using SEP as
        a separator in place of os.path.sep).
        """
        logger.info(bold(__('updating environment: ')), nonl=True)

        self.env.find_files(self.config, self)
        updated = (self.env.config_status != CONFIG_OK)
        added, changed, removed = self.env.get_outdated_files(updated)

        # allow user intervention as well
        for docs in self.events.emit('env-get-outdated', self.env, added, changed, removed):
            changed.update(set(docs) & self.env.found_docs)

        # if files were added or removed, all documents with globbed toctrees
        # must be reread
        if added or removed:
            # ... but not those that already were removed
            changed.update(self.env.glob_toctrees & self.env.found_docs)

        if updated:  # explain the change iff build config status was not ok
            reason = (CONFIG_CHANGED_REASON.get(self.env.config_status, '') +
                      (self.env.config_status_extra or ''))
            logger.info('[%s] ', reason, nonl=True)

        logger.info(__('%s added, %s changed, %s removed'),
                    len(added), len(changed), len(removed))

        # clear all files no longer present
        for docname in removed:
            self.events.emit('env-purge-doc', self.env, docname)
            self.env.clear_doc(docname)

        # read all new and changed files
        docnames = sorted(added | changed)
        # allow changing and reordering the list of docs to read
        self.events.emit('env-before-read-docs', self.env, docnames)

        # check if we should do parallel or serial read
        if len(docnames) > 5 and self.app.parallel > 1 and self.app.is_parallel_allowed('read'):
            self._read_parallel(docnames, nproc=self.app.parallel)
        else:
            self._read_serial(docnames)

        if self.config.root_doc not in self.env.all_docs:
            raise SphinxError('root file %s not found' %
                              self.env.doc2path(self.config.root_doc))

        for retval in self.events.emit('env-updated', self.env):
            if retval is not None:
                docnames.extend(retval)

        # workaround: marked as okay to call builder.read() twice in same process
        self.env.config_status = CONFIG_OK

        return sorted(docnames)

    def _read_serial(self, docnames: List[str]) -> None:
        for docname in status_iterator(docnames, __('reading sources... '), "purple",
                                       len(docnames), self.app.verbosity):
            # remove all inventory entries for that file
            self.events.emit('env-purge-doc', self.env, docname)
            self.env.clear_doc(docname)
            self.read_doc(docname)

    def _read_parallel(self, docnames: List[str], nproc: int) -> None:
        # clear all outdated docs at once
        for docname in docnames:
            self.events.emit('env-purge-doc', self.env, docname)
            self.env.clear_doc(docname)
        app = types.SimpleNamespace(
            config=self.app.config,
            env=self.env,
            registry=self.app.registry
        )
        # parallel.parallel_status_iterator(
        #     nproc,
        #     docnames,
        #     __('reading sources... '),
        #     "purple",
        #     self.app.verbosity,
        #     None,
        #     _read_process,
        #     _merge_from_process,
        #     (self.env, app, self.confdir, self.doctreedir, self.config.default_role)
        # )
        with multiprocessing.pool.Pool(nproc, context=multiprocessing.context.SpawnContext()) as pool:
            result = pool.apply_async(
                _read_process,
                (docnames[:10], self.env, app, self.confdir, self.doctreedir, self.config.default_role),
                {},
                _merge_from_process
            )

            # make sure all threads have finished
            logger.info(bold(__('waiting for workers...')))

            while not result.ready():
                result.wait(0.01)

            ret = result.get(timeout=0)
            if not result.successful():
                raise RuntimeError("!!!") from ret


    def read_doc(self, docname: str) -> None:
        """Parse a file and add/update inventory entries for the doctree."""
        read_doc(docname, self.env, self.app, self.confdir, self.doctreedir, self.config.default_role)

    def write_doctree(self, docname: str, doctree: nodes.document) -> None:
        """Write the doctree to a file."""
        warnings.warn("sphinx.builders.Builder.write_doctree is deprecated, use"
                      "sphinx.builders.write_doctree instead.",
                      RemovedInSphinx70Warning, stacklevel=2)
        write_doctree(doctree, self.doctreedir, docname)

    def write(self, build_docnames: Iterable[str], updated_docnames: Sequence[str], method: str = 'update') -> None:  # NOQA
        if build_docnames is None or build_docnames == ['__all__']:
            # build_all
            build_docnames = self.env.found_docs
        if method == 'update':
            # build updated ones as well
            docnames = set(build_docnames) | set(updated_docnames)
        else:
            docnames = set(build_docnames)
        logger.debug(__('docnames to write: %s'), ', '.join(sorted(docnames)))

        # add all toctree-containing files that may have changed
        for docname in list(docnames):
            for tocdocname in self.env.files_to_rebuild.get(docname, set()):
                if tocdocname in self.env.found_docs:
                    docnames.add(tocdocname)
        docnames.add(self.config.root_doc)

        with progress_message(__('preparing documents')):
            self.prepare_writing(docnames)

        if self.parallel_ok:
            # number of subprocesses is parallel-1 because the main process
            # is busy loading doctrees and doing write_doc_serialized()
            self._write_parallel(sorted(docnames),
                                 nproc=self.app.parallel - 1)
        else:
            self._write_serial(sorted(docnames))

    def _write_serial(self, docnames: Sequence[str]) -> None:
        with logging.pending_warnings():
            for docname in status_iterator(docnames, __('writing output... '), "darkgreen",
                                           len(docnames), self.app.verbosity):
                self.app.phase = BuildPhase.RESOLVING
                doctree = self.env.get_and_resolve_doctree(docname, self)
                self.app.phase = BuildPhase.WRITING
                self.write_doc_serialized(docname, doctree)
                self.write_doc(docname, doctree)

    def _write_parallel(self, docnames: Sequence[str], nproc: int) -> None:
        def chunk_preprocessor(chunk: List[str]):
            arg = []
            for docname in chunk:
                doctree = self.env.get_and_resolve_doctree(docname, self)
                self.write_doc_serialized(docname, doctree)
                arg.append((docname, doctree))

        def write_process(docs: List[Tuple[str, nodes.document]]) -> None:
            for docname, doctree in docs:
                self.write_doc(docname, doctree)

        # warm up caches/compile templates using the first document
        firstname, docnames = docnames[0], docnames[1:]
        self.app.phase = BuildPhase.RESOLVING
        doctree = self.env.get_and_resolve_doctree(firstname, self)
        self.app.phase = BuildPhase.WRITING
        self.write_doc_serialized(firstname, doctree)
        self.write_doc(firstname, doctree)

        parallel.parallel_status_iterator(
            nproc,
            docnames,
            __('writing output... '),
            "darkgreen",
            self.app.verbosity,
            chunk_preprocessor,
            write_process,
            None
        )


    def prepare_writing(self, docnames: Set[str]) -> None:
        """A place where you can add logic before :meth:`write_doc` is run"""
        raise NotImplementedError

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        """Where you actually write something to the filesystem."""
        raise NotImplementedError

    def write_doc_serialized(self, docname: str, doctree: nodes.document) -> None:
        """Handle parts of write_doc that must be called in the main process
        if parallel build is active.
        """
        pass

    def finish(self) -> None:
        """Finish the building process.

        The default implementation does nothing.
        """
        pass

    def cleanup(self) -> None:
        """Cleanup any resources.

        The default implementation does nothing.
        """
        pass

    def get_builder_config(self, option: str, default: str) -> Any:
        """Return a builder specific option.

        This method allows customization of common builder settings by
        inserting the name of the current builder in the option key.
        If the key does not exist, use default as builder name.
        """
        # At the moment, only XXX_use_index is looked up this way.
        # Every new builder variant must be registered in Config.config_values.
        try:
            optname = '%s_%s' % (self.name, option)
            return getattr(self.config, optname)
        except AttributeError:
            optname = '%s_%s' % (default, option)
            return getattr(self.config, optname)


def _read_process(docs: List[str], env, app, confdir, doctreedir, default_role_name) -> BuildEnvironment:
    for docname in docs:
        read_doc(docname, env, app, confdir, doctreedir, default_role_name)
    return env


def _merge_from_process(self: Builder, app, result: Dict[str, Any]) -> None:
    otherenv = result["value"]
    docs = result["arg"]
    self.env.merge_info_from(docs, otherenv, app)


def read_doc(docname: str, env: BuildEnvironment, app: "Sphinx", confdir: str, doctreedir: str, default_role_name: str) -> None:
    """Parse a file and add/update inventory entries for the doctree."""
    env.prepare_settings(docname)

    # Add confdir/docutils.conf to dependencies list if exists
    docutilsconf = path.join(confdir, 'docutils.conf')
    if path.isfile(docutilsconf):
        env.note_dependency(docutilsconf)

    filename = env.doc2path(docname)
    filetype = get_filetype(app.config.source_suffix, filename)
    publisher = app.registry.get_publisher(app, filetype)
    with sphinx_domains(env), rst.default_role(docname, default_role_name):
        # set up error_handler for the target document
        codecs.register_error('sphinx', UnicodeDecodeErrorHandler(docname))  # type: ignore

        publisher.set_source(source_path=filename)
        publisher.publish()
        doctree = publisher.document

    # store time of reading, for outdated files detection
    # (Some filesystems have coarse timestamp resolution;
    # therefore time.time() can be older than filesystem's timestamp.
    # For example, FAT32 has 2sec timestamp resolution.)
    env.all_docs[docname] = max(time.time(), path.getmtime(filename))

    # cleanup
    env.temp_data.clear()
    env.ref_context.clear()

    write_doctree(doctree, doctreedir, docname)


def write_doctree(doctree: nodes.document, doctreedir: str, docname: str) -> None:
    """Write the doctree to a file."""

    # Create a copy of the settings object before modification as it is shared
    # with other documents.
    doctree.settings = doctree.settings.copy()

    # make the doctree picklable
    doctree.reporter = None
    doctree.transformer = None
    doctree.settings.warning_stream = None
    doctree.settings.env = None
    doctree.settings.record_dependencies = None

    doctree_filename = path.join(doctreedir, docname + '.doctree')
    ensuredir(path.dirname(doctree_filename))
    with open(doctree_filename, 'wb') as f:
        pickle.dump(doctree, f, pickle.HIGHEST_PROTOCOL)
