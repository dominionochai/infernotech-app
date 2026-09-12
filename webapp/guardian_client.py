"""
Real client for Hedera Guardian's external-data-source MRV API.

Guardian (https://github.com/hashgraph/guardian) is Hedera's open-source
platform for tokenizing environmental assets (carbon credits) under
Verra/Gold-Standard-style methodologies, enforced by a policy workflow
engine and recorded on the Hedera public ledger. A live Guardian instance
runs one or more published *policies* — VM0015 "Avoided Unplanned
Deforestation" (github.com/hashgraph/guardian PR #3516) is one of them.

External systems feed a running policy with monitoring data (an "MRV" —
Monitoring, Reporting, Verification — document) via Guardian's documented
external-data-source API:

    POST {GUARDIAN_API_URL}/external
    {
      "owner": "<DID of the registered installer/device on that policy>",
      "policyTag": "<the policy's external-data tag, e.g. 'MRV_VM0015'>",
      "document": { ...schema-specific VC document fields... }
    }

This requires an ALREADY RUNNING, ALREADY CONFIGURED Guardian instance with
the VM0015 policy imported and an owner DID registered against it — Guardian
itself is a large multi-service platform (guardian-service, worker-service,
mrv-sender, MongoDB, IPFS, a Hedera testnet/mainnet account) that is out of
scope to stand up here. This module is the correct, documented integration
point for InfernoTech to talk to one, once you have it running.

The exact `document` field names must match VM0015's actual schema (the
.policy/schema files from the PR) — build_vm0015_mrv_document() below uses
a reasonable placeholder shape based on what the methodology monitors
(protected area, monitoring period, avoided-deforestation evidence) and
should be reconciled against your actual imported schema before relying on
it to mint real credits.
"""
import json
import os
import urllib.error
import urllib.request

USER_AGENT = "infernotech-unified-wildfire-platform/1.0"


class GuardianError(Exception):
    pass


def _config():
    api_url = os.environ.get("GUARDIAN_API_URL")
    owner_did = os.environ.get("GUARDIAN_OWNER_DID")
    policy_tag = os.environ.get("GUARDIAN_POLICY_TAG", "MRV_VM0015")
    token = os.environ.get("GUARDIAN_ACCESS_TOKEN")

    missing = [name for name, val in [
        ("GUARDIAN_API_URL", api_url),
        ("GUARDIAN_OWNER_DID", owner_did),
    ] if not val]
    if missing:
        raise GuardianError(
            f"Guardian not configured — missing env var(s): {', '.join(missing)}. "
            "Set these once you have a running Guardian instance with VM0015 "
            "imported and an owner DID registered against it."
        )
    return api_url.rstrip("/"), owner_did, policy_tag, token


def build_vm0015_mrv_document(location_name, lat, lon, protected_area_ha,
                               monitoring_start, monitoring_end, evidence_source):
    """Builds a placeholder VM0015-shaped MRV document. Field names here are
    a reasonable approximation of what the "Avoided Unplanned Deforestation"
    methodology monitors — reconcile against your actual imported policy
    schema (from the PR's .policy/schema files) before submitting for real
    credit issuance. See https://verra.org/methodologies/vm0015-methodology-for-avoided-unplanned-deforestation-v1-1/
    """
    return {
        "type": ["VerifiableCredential"],
        "credentialSubject": [{
            "projectLocation": location_name,
            "latitude": lat,
            "longitude": lon,
            "protectedAreaHectares": protected_area_ha,
            "monitoringPeriodStart": monitoring_start,
            "monitoringPeriodEnd": monitoring_end,
            "avoidedDeforestationEvidence": evidence_source,
            "methodology": "VM0015",
        }],
    }


def submit_mrv(document):
    """POSTs an MRV document to a running Guardian instance's external-data
    API. Raises GuardianError on missing config or a failed request —
    callers should catch this and fall back gracefully, same pattern as
    fire_data.py and weather.py."""
    api_url, owner_did, policy_tag, token = _config()

    payload = {
        "owner": owner_did,
        "policyTag": policy_tag,
        "document": document,
    }
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{api_url}/external",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise GuardianError(f"Guardian API error {e.code}: {body[:500]}")
    except urllib.error.URLError as e:
        raise GuardianError(f"Could not reach Guardian at {api_url}: {e}")
