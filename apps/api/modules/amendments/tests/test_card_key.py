from modules.amendments.domain.card_key import generate_card_key


def test_generate_card_key_basic():
    key = generate_card_key(
        law_key="cgst_act_2017",
        provision_label="Section 17(5)(d)",
        change_type="modification",
    )
    assert key == "cgst-act-2017:section-175d:modification"


def test_generate_card_key_with_title():
    key = generate_card_key(
        law_key="income_tax_act_1961",
        provision_label="Section 115BAC",
        change_type="modification",
        title="New tax slab revisions for individual assessee",
    )
    assert key.startswith("income-tax-act-1961:section-115bac:modification:new-tax-slab-revisions")


def test_generate_card_key_stability():
    k1 = generate_card_key("customs_act", "Section 28", "addition")
    k2 = generate_card_key("customs_act", "Section 28", "addition")
    assert k1 == k2


def test_generate_card_key_handles_special_characters_and_length():
    key = generate_card_key(
        law_key="Companies Act, 2013 & Rules!!!",
        provision_label="Rule 3(1) [Proviso 2]",
        change_type="clarification",
    )
    assert "companies-act-2013-rules" in key
    assert "rule-31-proviso-2" in key
    assert len(key) <= 120
