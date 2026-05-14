"""CWE -> MITRE ATT&CK technique mapping (curated)."""
from __future__ import annotations
from typing import Dict, List

_CWE_TO_ATTACK: Dict[str, List[Dict[str, str]]] = {
    "CWE-119": [{"id": "T1203", "name": "Exploitation for Client Execution"},
                {"id": "T1068", "name": "Exploitation for Privilege Escalation"}],
    "CWE-120": [{"id": "T1203", "name": "Exploitation for Client Execution"}],
    "CWE-122": [{"id": "T1203", "name": "Exploitation for Client Execution"},
                {"id": "T1190", "name": "Exploit Public-Facing Application"}],
    "CWE-125": [{"id": "T1005", "name": "Data from Local System"},
                {"id": "T1212", "name": "Exploitation for Credential Access"}],
    "CWE-416": [{"id": "T1203", "name": "Exploitation for Client Execution"},
                {"id": "T1068", "name": "Exploitation for Privilege Escalation"}],
    "CWE-415": [{"id": "T1499", "name": "Endpoint Denial of Service"}],
    "CWE-476": [{"id": "T1499", "name": "Endpoint Denial of Service"}],
    "CWE-401": [{"id": "T1499", "name": "Endpoint Denial of Service"}],
    "CWE-190": [{"id": "T1203", "name": "Exploitation for Client Execution"}],
    "CWE-191": [{"id": "T1203", "name": "Exploitation for Client Execution"}],
    "CWE-369": [{"id": "T1499", "name": "Endpoint Denial of Service"}],
    "CWE-197": [{"id": "T1203", "name": "Exploitation for Client Execution"}],
    "CWE-680": [{"id": "T1203", "name": "Exploitation for Client Execution"}],
    "CWE-89":  [{"id": "T1190", "name": "Exploit Public-Facing Application"},
                {"id": "T1213", "name": "Data from Information Repositories"}],
    "CWE-78":  [{"id": "T1059", "name": "Command and Scripting Interpreter"},
                {"id": "T1190", "name": "Exploit Public-Facing Application"}],
    "CWE-611": [{"id": "T1005", "name": "Data from Local System"},
                {"id": "T1190", "name": "Exploit Public-Facing Application"}],
    "CWE-918": [{"id": "T1190", "name": "Exploit Public-Facing Application"},
                {"id": "T1090", "name": "Proxy"}],
    "CWE-639": [{"id": "T1190", "name": "Exploit Public-Facing Application"}],
    "CWE-134": [{"id": "T1203", "name": "Exploitation for Client Execution"}],
    "CWE-73":  [{"id": "T1083", "name": "File and Directory Discovery"},
                {"id": "T1005", "name": "Data from Local System"}],
    "CWE-326": [{"id": "T1040", "name": "Network Sniffing"},
                {"id": "T1557", "name": "Adversary-in-the-Middle"}],
    "CWE-327": [{"id": "T1040", "name": "Network Sniffing"},
                {"id": "T1557", "name": "Adversary-in-the-Middle"}],
    "CWE-330": [{"id": "T1606", "name": "Forge Web Credentials"}],
    "CWE-798": [{"id": "T1078", "name": "Valid Accounts"},
                {"id": "T1552", "name": "Unsecured Credentials"}],
    "CWE-287": [{"id": "T1078", "name": "Valid Accounts"},
                {"id": "T1212", "name": "Exploitation for Credential Access"}],
    "CWE-311": [{"id": "T1040", "name": "Network Sniffing"}],
}


def attack_techniques_for_cwe(cwe: str) -> List[Dict[str, str]]:
    return list(_CWE_TO_ATTACK.get((cwe or "").upper(), []))
