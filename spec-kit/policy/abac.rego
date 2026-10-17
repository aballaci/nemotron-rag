package rag.authz

default allow = false

allow if {
    user.employment_status == "active"
    user.clearance_level >= resource.confidentiality_level
    user.department == resource.department
    input.action == "read"
}

deny if {
    not allow
}
