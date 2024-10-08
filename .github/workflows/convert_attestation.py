from pathlib import Path
from pypi_attestations import Attestation
from sigstore.models import Bundle

# Sigstore Bundle -> PEP 740 Attestation object
filename = 'test_package-0.0.1-py3-none-any.whl'
bundle_path = Path(f'{filename}.sigstore')
sigstore_bundle = Bundle.from_json(bundle_path.read_bytes())
attestation = Attestation.from_bundle(sigstore_bundle)
print(attestation.model_dump_json())
signature_path = Path(f"{filename}.publish.attestation")
signature_path.write_text(attestation.model_dump_json())
print(f"Attestation for {filename} written to {signature_path}")
