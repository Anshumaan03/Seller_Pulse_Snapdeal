from app import nlu


def test_days():
    assert nlu.extract_days("I can restock it in three days") == 3
    assert nlu.extract_days("maybe 2 weeks") == 14
    assert nlu.extract_days("tomorrow") == 1
    assert nlu.extract_days("teen din mein") == 3
    assert nlu.extract_days("sometime") is None


def test_amount():
    assert nlu.extract_amount("my minimum is ₹850") == 850
    assert nlu.extract_amount("850 rupees") == 850
    assert nlu.extract_amount("Rs. 1,050") == 1050
    assert nlu.extract_amount("850", expect_amount=True) == 850
    assert nlu.extract_amount("3 days", expect_amount=True) is None   # a day count is not a price
    assert nlu.extract_amount("850") is None                          # no context, no guess


def test_price_policy():
    assert nlu.extract_price_policy("I can review the price, but do not reduce it automatically.") == "manual_only"
    assert nlu.extract_price_policy("I cannot reduce the price at all") == "no_cut"
    assert nlu.extract_price_policy("I can reduce a little") == "open"
    assert nlu.extract_price_policy("hmm") is None


def test_yes_no():
    assert nlu.is_yes("yes that sounds good") and nlu.is_yes("haan theek hai")
    assert nlu.is_no("no") and nlu.is_no("nahi")
    assert not nlu.is_no("no problem")
    assert not nlu.is_yes("no, don't save it")


def test_misc_intents():
    assert nlu.is_repeat("can you repeat that")
    assert nlu.is_not_now("not now, I'm busy")
    assert nlu.is_dont_know("I don't know")
    assert nlu.is_wrong_number("that number is wrong")
    assert nlu.is_promo("should I run ads or a discount?")
    assert nlu.classify_concern("my page visits have dropped") == "visits"
    assert nlu.classify_concern("revenue is low") == "revenue"
    assert nlu.mentioned_sku("what about the bedsheet") == "DEMO-SKU-02"


def test_removal_and_restock():
    assert nlu.extract_removal("skip the jar one") == {"dispatch_fix"}
    assert nlu.extract_removal("drop the price review") == {"price_review", "price_test"}
    assert nlu.extract_removal("sounds good") == set()
    assert nlu.extract_restock("I don't have stock", asked=True) == ("none", None)
    assert nlu.extract_restock("yes", asked=True) == ("soon", 7)
    assert nlu.extract_restock("I'm not sure", asked=True) == ("unknown", None)
    assert nlu.extract_restock("yes", asked=False) == (None, None)


def test_hinglish_basics():
    assert nlu.extract_price_policy("price kam nahi karunga") == "no_cut"
    assert nlu.extract_days("teen din mein aa jayega") == 3
    assert nlu.is_yes("haan theek hai")
    assert nlu.classify_concern("mere orders kam ho gaye hain") == "orders"
