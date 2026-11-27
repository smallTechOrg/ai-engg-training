"""The curriculum definition, the folders on disk and the generated pages must agree."""

from labkit.catalog import find_lesson, load_catalog, render_map, scenario, sync_module_readme
from labkit.config import repo_root

MODULES = load_catalog()
LESSONS = [item for module in MODULES for item in module.lessons]


def test_ids_are_unique_and_ordered():
    assert [m.id for m in MODULES] == [f"{n:02d}" for n in range(len(MODULES))]
    ids = [item.id for item in LESSONS]
    assert len(ids) == len(set(ids))
    for module in MODULES:
        assert [item.id for item in module.lessons] == [f"{module.id}.{n}" for n in range(1, len(module.lessons) + 1)]


def test_every_module_has_a_folder_and_readme():
    for module in MODULES:
        assert (module.path / "README.md").is_file(), module.slug


def test_runnable_lessons_are_complete():
    runnable = [item for item in LESSONS if item.runnable]
    assert runnable, "at least one lesson must be ready"
    for item in runnable:
        readme = item.path / "README.md"
        assert readme.is_file(), f"{item.id} has no README"
        assert item.scripts(), f"{item.id} has no scripts"
        text = readme.read_text(encoding="utf-8")
        for section in ("## What you will learn", "```mermaid", "Expected output", "## Try this"):
            assert section in text, f"{item.id} README lacks: {section}"
        for script in item.scripts():
            assert script.name in text, f"{item.id} README does not mention {script.name}"


def test_planned_lessons_have_no_stray_folders():
    for item in LESSONS:
        if not item.runnable:
            assert not item.path.exists(), f"{item.id} is planned but has a folder: mark it draft or ready"


def test_generated_pages_are_in_sync():
    hint = "run `./run map` and commit the result"
    current = (repo_root() / "CURRICULUM.md").read_text(encoding="utf-8")
    assert current == render_map(MODULES, scenario()), hint
    for module in MODULES:
        text = (module.path / "README.md").read_text(encoding="utf-8")
        assert text == sync_module_readme(text, module, scenario()), f"{module.slug}: {hint}"


def test_lesson_targets_resolve():
    assert find_lesson(MODULES, "01.1")[0].id == "01.1"
    assert find_lesson(MODULES, "1.1/2") == (find_lesson(MODULES, "01.1")[0], 2)
    assert find_lesson(MODULES, "99.9")[0] is None


def test_no_secrets_template_drift():
    example = (repo_root() / ".env.example").read_text(encoding="utf-8")
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "EMBEDDING_MODEL"):
        assert name in example
