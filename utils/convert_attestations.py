import base64
import json
import sys
from pathlib import Path

from pypi_attestations import Attestation
from sigstore.models import Bundle

DIST = Path('dist')

bundle_path = Path(sys.argv[1])
for line in bundle_path.read_bytes().splitlines():
    dsse_envelope_payload = json.loads(line)['dsseEnvelope']['payload']
    subjects = json.loads(base64.b64decode(dsse_envelope_payload))['subject']
    for subject in subjects:
        filename = subject['name']
        print(f'Converting attestation for {filename}')
        sigstore_bundle = Bundle.from_json(line)
        attestation = Attestation.from_bundle(sigstore_bundle)
        print(attestation.model_dump_json())
        signature_path = DIST / f'{filename}.publish.attestation'
        signature_path.write_text(attestation.model_dump_json())
        print(f'Attestation for {filename} written to {signature_path}')
        print()
