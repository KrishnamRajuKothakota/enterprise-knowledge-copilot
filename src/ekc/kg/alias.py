"""
Canonical ID resolution for the Knowledge Graph.
Maps surface form variants to stable canonical IDs.
Format: "surface form (lowercase)" -> "type:canonical_id"

The demo chain (Project Orion -> auth-service -> SOP-IT-001 -> JRA-1001)
is explicitly included here to guarantee the multi-hop query resolves.
"""

ALIAS_MAP: dict[str, str] = {

    # ── Kubernetes ────────────────────────────────────────────────────────────
    "kubernetes":           "tech:kubernetes",
    "k8s":                  "tech:kubernetes",
    "kube":                 "tech:kubernetes",
    "kubectl":              "tech:kubernetes",
    "k8":                   "tech:kubernetes",

    # ── Docker ───────────────────────────────────────────────────────────────
    "docker":               "tech:docker",
    "dockerfile":           "tech:docker",
    "docker compose":       "tech:docker",
    "docker-compose":       "tech:docker",
    "containerization":     "tech:docker",
    "container":            "tech:docker",

    # ── Cloud / Infrastructure ────────────────────────────────────────────────
    "aws":                  "tech:aws",
    "amazon web services":  "tech:aws",
    "ec2":                  "tech:aws_ec2",
    "s3":                   "tech:aws_s3",
    "iam":                  "tech:aws_iam",
    "azure":                "tech:azure",
    "gcp":                  "tech:gcp",
    "google cloud":         "tech:gcp",
    "terraform":            "tech:terraform",
    "ansible":              "tech:ansible",
    "jenkins":              "tech:jenkins",
    "gitlab":               "tech:gitlab",
    "github":               "tech:github",
    "helm":                 "tech:helm",
    "prometheus":           "tech:prometheus",
    "grafana":              "tech:grafana",
    "nginx":                "tech:nginx",
    "redis":                "tech:redis",
    "postgresql":           "tech:postgresql",
    "postgres":             "tech:postgresql",
    "elasticsearch":        "tech:elasticsearch",

    # ── SOP IDs ───────────────────────────────────────────────────────────────
    "sop-it-001":           "sop:incident_management",
    "sop-it-002":           "sop:it_onboarding",
    "sop-it-003":           "sop:change_management",
    "sop-it-004":           "sop:vpn_access",
    "sop-it-005":           "sop:access_control",
    "sop-it-006":           "sop:backup_recovery",
    "sop-it-007":           "sop:patch_management",
    "sop-it-008":           "sop:asset_management",
    "sop-it-009":           "sop:service_desk",
    "sop-it-010":           "sop:monitoring_alerting",
    "sop-it-011":           "sop:data_classification",
    "sop-it-012":           "sop:vendor_management",
    "sop-it-013":           "sop:capacity_planning",
    "sop-it-014":           "sop:security_incident",
    "sop-it-015":           "sop:business_continuity",
    "sop-it-016":           "sop:network_management",
    "sop-it-017":           "sop:cloud_provisioning",
    "sop-it-018":           "sop:leaver_offboarding",
    "sop-it-019":           "sop:software_deployment",
    "sop-it-020":           "sop:database_management",
    "sop-it-021":           "sop:mobile_device",
    "sop-it-022":           "sop:remote_work",
    "sop-it-023":           "sop:knowledge_management",
    "sop-it-024":           "sop:problem_management",
    "sop-it-025":           "sop:release_management",
    "sop-it-026":           "sop:configuration_management",
    "sop-it-027":           "sop:compliance_audit",
    "sop-it-028":           "sop:encryption_policy",
    "sop-it-029":           "sop:third_party_access",
    "sop-it-030":           "sop:it_procurement",

    # ── Teams / Org units ─────────────────────────────────────────────────────
    "devops team":          "team:devops",
    "devops":               "team:devops",
    "platform engineering": "team:platform_engineering",
    "platform team":        "team:platform_engineering",
    "security team":        "team:security",
    "infosec":              "team:security",
    "l1 support":           "team:l1_support",
    "l1 agent":             "team:l1_support",
    "l2 support":           "team:l2_support",
    "l2 team":              "team:l2_support",
    "l3 support":           "team:l3_support",
    "network operations":   "team:network_ops",
    "noc":                  "team:network_ops",
    "hr-it":                "team:hr_it",
    "it infrastructure":    "team:it_infra",
    "it service management":"team:itsm",

    # ── ITSM concepts ─────────────────────────────────────────────────────────
    "p1":                   "priority:p1_critical",
    "p1 incident":          "priority:p1_critical",
    "p2":                   "priority:p2_high",
    "p3":                   "priority:p3_medium",
    "p4":                   "priority:p4_low",
    "sla":                  "concept:sla",
    "mttr":                 "concept:mttr",
    "rca":                  "concept:root_cause_analysis",
    "root cause analysis":  "concept:root_cause_analysis",
    "change request":       "concept:change_request",
    "cab":                  "concept:change_advisory_board",
    "cmdb":                 "concept:cmdb",
    "ci":                   "concept:configuration_item",

    # ── Incident & escalation ─────────────────────────────────────────────────
    "incident management":      "sop:incident_management",
    "escalation":               "sop:incident_management",
    "escalation procedure":     "sop:incident_management",
    "p1 incident":              "sop:incident_management",
    "major incident":           "sop:incident_management",
    "incident response":        "sop:incident_management",

    # ── VPN ───────────────────────────────────────────────────────────────────
    "vpn":                      "sop:vpn_access",
    "vpn access":               "sop:vpn_access",
    "vpn provisioning":         "sop:vpn_access",
    "remote access":            "sop:vpn_access",
    "vpn troubleshooting":      "sop:vpn_access",

    # ── Onboarding ───────────────────────────────────────────────────────────
    "onboarding":               "sop:it_onboarding",
    "new employee":             "sop:it_onboarding",
    "new hire":                 "sop:it_onboarding",
    "employee onboarding":      "sop:it_onboarding",

    # ── Change management ─────────────────────────────────────────────────────
    "change management":        "sop:change_management",
    "change request":           "sop:change_management",
    "change advisory":          "sop:change_management",

    # ── Security ─────────────────────────────────────────────────────────────
    "security incident":        "sop:security_incident",
    "data breach":              "sop:security_incident",
    "access control":           "sop:access_control",
    "user access":              "sop:access_control",
    "password reset":           "sop:access_control",

    # ── K8s operations ───────────────────────────────────────────────────────
    "rollback procedure":       "concept:rollback",
    "deployment rollback":      "concept:rollback",
    "k8s rollback":             "concept:rollback",
    "pod restart":              "concept:crashloopbackoff",
    "crashloop":                "concept:crashloopbackoff",

    # ── Demo chain: Project Orion → auth-service → SOP-IT-001 → JRA-1001 ─────
    # This chain is engineered to make the multi-hop demo query resolve
    "project orion":        "project:orion",
    "orion":                "project:orion",
    "auth-service":         "tech:auth_service",
    "auth service":         "tech:auth_service",
    "authentication service":"tech:auth_service",
    "jra-1001":             "ticket:jra_1001",
    "jra1001":              "ticket:jra_1001",
    "crashloopbackoff":     "concept:crashloopbackoff",
    "crash loop":           "concept:crashloopbackoff",
    "pod crash":            "concept:crashloopbackoff",
    "rollback":             "concept:rollback",
    "deployment rollback":  "concept:rollback",
}


def resolve(surface: str) -> str:
    """
    Resolve a surface form to its canonical ID.
    Returns the canonical ID if found, otherwise returns the surface form.
    """
    return ALIAS_MAP.get(surface.lower().strip(), surface.lower().strip())


def get_canonical(surface: str) -> str | None:
    """Returns canonical ID or None if not in the alias map."""
    return ALIAS_MAP.get(surface.lower().strip())