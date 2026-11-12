"""Anchor indexes must describe the resources currently registered."""

import pytest

from referencing import Registry, exceptions
from referencing.jsonschema import DRAFT202012

URI = "https://example.test/root"


def resource(name, value):
    return DRAFT202012.create_resource(
        {"$id": URI, "$anchor": name, "const": value},
    )


@pytest.mark.parametrize("crawl_replacement", [False, True])
@pytest.mark.parametrize("method", ["single", "batch", "matmul", "combine"])
def test_replacement_discards_old_anchors(method, crawl_replacement):
    old = resource("old", 1)
    new = resource("new", 2)
    original = Registry().with_resource(URI, old).crawl()
    if method == "single":
        changed = original.with_resource(URI, new)
    elif method == "batch":
        changed = original.with_resources([(URI, new)])
    elif method == "matmul":
        changed = new @ original
    else:
        changed = original.combine(Registry().with_resource(URI, new))
    if crawl_replacement:
        changed = changed.crawl()

    assert changed.contents(URI) == new.contents
    with pytest.raises(exceptions.NoSuchAnchor):
        changed.anchor(URI, "old")
    assert changed.anchor(URI, "new").value.resource.contents == new.contents
    assert original.anchor(URI, "old").value.resource.contents == old.contents


@pytest.mark.parametrize("incoming_crawled", [False, True])
def test_same_name_anchor_uses_new_resource(incoming_crawled):
    old = resource("same", 1)
    new = resource("same", 2)
    original = Registry().with_resource(URI, old).crawl()
    incoming = Registry().with_resource(URI, new)
    if incoming_crawled:
        incoming = incoming.crawl()
    changed = original.combine(incoming)
    assert changed.anchor(URI, "same").value.resource.contents == new.contents
    assert original.anchor(URI, "same").value.resource.contents == old.contents


def test_replacement_preserves_other_resources_anchors():
    other_uri = "https://example.test/other"
    other = DRAFT202012.create_resource({"$anchor": "untouched", "const": 3})
    original = (
        Registry()
        .with_resources(
            [(URI, resource("old", 1)), (other_uri, other)],
        )
        .crawl()
    )
    changed = original.with_resources(
        [(URI + "#", resource("discarded", 2)), (URI, resource("new", 4))],
    )
    assert changed.anchor(other_uri, "untouched").value.resource == other
    assert changed.anchor(URI, "new").value.resource.contents["const"] == 4
    for name in ["old", "discarded"]:
        with pytest.raises(exceptions.NoSuchAnchor):
            changed.anchor(URI, name)


def test_combining_identical_resource_preserves_crawled_anchor_index():
    original_resource = resource("same", 1)
    original = Registry().with_resource(URI, original_resource).crawl()
    changed = original.combine(Registry({URI: original_resource}))
    assert changed.anchor(URI, "same").value.resource == original_resource


def test_reregistering_identical_resource_preserves_anchor_index():
    original_resource = resource("same", 1)
    original = Registry().with_resource(URI, original_resource).crawl()
    changed = original.with_resource(URI, original_resource)
    assert changed.anchor(URI, "same").value.resource == original_resource


def test_replacement_discards_nested_anchors_in_same_resource_only():
    nested = DRAFT202012.create_resource(
        {
            "$id": URI,
            "$defs": {
                "anonymous": {"$anchor": "nested"},
                "separate": {"$id": "child", "$anchor": "independent"},
            },
        },
    )
    original = Registry().with_resource(URI, nested).crawl()
    changed = original.with_resource(URI, resource("new", 2))
    with pytest.raises(exceptions.NoSuchAnchor):
        changed.anchor(URI, "nested")
    assert changed.anchor("https://example.test/child", "independent").value
    assert original.anchor(URI, "nested").value


def test_replacement_at_retrieval_alias_does_not_remove_canonical_anchor():
    old = resource("old", 1)
    alias = "https://example.test/retrieval"
    original = Registry().with_resource(alias, old).crawl()
    changed = original.with_resource(alias, DRAFT202012.create_resource({}))
    assert changed.anchor(URI, "old").value.resource == old


def test_relative_id_is_not_reapplied_to_replaced_canonical_root():
    seed = "https://example.test/x/y/a/root"
    canonical = "https://example.test/x/b/root"
    old = DRAFT202012.create_resource(
        {"$id": "../../b/root", "$anchor": "old"},
    )
    original = Registry().with_resource(seed, old).crawl()
    changed = original.with_resource(
        canonical,
        DRAFT202012.create_resource({"$anchor": "new"}),
    )
    with pytest.raises(exceptions.NoSuchAnchor):
        changed.anchor(canonical, "old")
    assert changed.anchor(canonical, "new").value
    assert original.anchor(canonical, "old").value.resource == old
