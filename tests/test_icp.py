from lead_qualifier.icp import dump_icp, icp_from_dict, load_icp


def test_default_icp_weights_sum_to_100():
    icp = load_icp()
    assert sum(icp.weights.values()) == 100
    assert icp.hot_threshold >= 80
    assert icp.hot_threshold > icp.warm_threshold
    assert "SaaS" in icp.industries["primary"]


def test_round_trip_dict():
    icp = load_icp()
    clone = icp_from_dict(dump_icp(icp))
    assert clone.weights == icp.weights
    assert clone.seller.name == icp.seller.name
    assert clone.hot_threshold == icp.hot_threshold
