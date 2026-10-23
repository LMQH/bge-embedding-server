from itertools import chain

from bge_embedding.inference import batch_groups


def test_groups_are_disjoint_ordered_and_preserve_indices():
    lengths = [25, 64, 128, 256, 512, 768, 1024, 25, 100, 300, 700, 900, 1200, 1500, 2000, 2048]
    groups = batch_groups(lengths)
    assert sorted(chain.from_iterable(groups)) == list(range(len(lengths)))
    assert all(group for group in groups)
    assert all(len(group) <= 16 for group in groups)


def test_groups_respect_padded_token_budget_and_length_ratio():
    for lengths in ([8192] * 4, [1024] * 16, [512] * 16, [25] * 16,
                    [25, 64, 128, 256, 512, 768, 1024, 1200, 1500, 2000, 2048],
                    [100] * 17):
        groups = batch_groups(lengths)
        for group in groups:
            padded = max(lengths[index] for index in group) * len(group)
            assert padded <= 8192
            assert (max(lengths[index] for index in group)
                    <= min(lengths[index] for index in group) * 1.25)


def test_group_sizes_match_padded_budget():
    assert [len(group) for group in batch_groups([25] * 16)] == [16]
    assert [len(group) for group in batch_groups([1024] * 16)] == [8, 8]
    assert [len(group) for group in batch_groups([8192] * 4)] == [1, 1, 1, 1]


def test_single_item_larger_than_budget_is_alone():
    assert batch_groups([20_000, 20_000]) == [[0], [1]]
