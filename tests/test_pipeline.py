from migrate import config as config_io
from migrate import pipeline, source


def run(config_path):
    return pipeline.run(config_io.load(config_path))


def outcome(result, entity, ext_id, line=None):
    return next(o for o in result.entities[entity].outcomes
                if o.external_id == ext_id and (line is None or o.line == line))


def test_reads_windows_1252_semicolon_exports(project):
    cfg = config_io.load(project())
    src = source.read(cfg.entity("accounts").source)
    assert src.encoding == "cp1252"
    assert src.delimiter == ";"
    assert "N° client" in src.headers
    assert src.rows[0]["Ville"] == "Bourg-en-Bresse"


def test_every_row_has_exactly_one_outcome(project):
    result = run(project())
    for name, ent in result.entities.items():
        counted = sum(ent.count(s) for s in pipeline.STATUSES)
        assert counted == len(ent.source.rows), name


def test_duplicate_siret_is_merged_into_most_complete_record(project):
    result = run(project())
    dup = outcome(result, "accounts", "CL002")
    assert dup.status == "merged"
    assert dup.merged_into == "CL001"
    assert result.entities["accounts"].merge_map == {"CL002": "CL001"}


def test_children_of_a_merged_duplicate_are_relinked_not_lost(project):
    result = run(project())
    contact = outcome(result, "contacts", "CT002")
    contract = outcome(result, "contracts", "CTR-2")
    assert contact.status == contract.status == "accepted"
    assert contact.record["account_external_id"] == "CL001"
    assert contract.record["account_external_id"] == "CL001"
    assert any("re-linked" in w for w in contact.warnings)


def test_rejected_parent_cascades_to_children(project):
    result = run(project())
    assert outcome(result, "accounts", "CL003").status == "rejected"
    child = outcome(result, "contacts", "CT003")
    assert child.status == "rejected"
    assert "was rejected" in child.reasons[0]


def test_orphan_is_rejected_with_a_reason_the_customer_can_act_on(project):
    result = run(project())
    orphan = outcome(result, "contacts", "CT004", line=5)
    assert orphan.status == "rejected"
    assert "does not exist in the accounts export" in orphan.reasons[0]


def test_duplicate_legacy_id_is_rejected(project):
    result = run(project())
    second = outcome(result, "contacts", "CT004", line=6)
    assert second.status == "rejected"
    assert "appears twice" in second.reasons[0]


def test_weak_duplicates_are_flagged_not_merged(project):
    result = run(project())
    a, b = outcome(result, "accounts", "CL004"), outcome(result, "accounts", "CL005")
    assert a.status == b.status == "accepted"
    assert any("possible duplicate of CL005" in w for w in a.warnings)


def test_out_of_scope_rows_are_skipped_not_rejected(project):
    result = run(project())
    assert outcome(result, "contracts", "CTR-4").status == "skipped"


def test_postcode_and_phone_are_repaired_not_rejected(project):
    result = run(project())
    acc = outcome(result, "accounts", "CL001")
    assert acc.status == "accepted"
    assert acc.record["postcode"] == "01000"
    assert acc.record["phone"] == "+33474223344"
