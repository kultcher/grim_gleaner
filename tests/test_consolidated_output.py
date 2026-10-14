from pathlib import Path

import pytest

from gd_affix_relevance.catalog import AffixCatalog
from gd_affix_relevance.domain import BuildProfile, RUSSIAN_LOCALE
from gd_affix_relevance.output import generate_consolidated_output
from gd_affix_relevance.output.consolidated_writer import BEGIN_BLOCK, GRADE_HISTORY
from test_grade_export import _catalog


def _sources(tmp_path):
    clean = tmp_path / 'clean'
    clean.mkdir()
    (clean / 'tagsgdx3_uimain.txt').write_text('tagDifficulty=Ascendant\ntagMenu=Menu\n', encoding='utf-8-sig')
    (clean / 'tags_items.txt').write_text('tagHealthy=Healthy\ntagUnused=Do not copy\n', encoding='utf-8-sig')
    return clean


def test_modern_master_preserves_colors_comments_blank_values_and_fills_individual_tags(tmp_path):
    clean = _sources(tmp_path)
    existing = tmp_path / 'installed'
    existing.mkdir()
    (existing / 'tagsgdx3_uimain.txt').write_text('# Custom colors\r\ntagDifficulty=Custom difficulty\r\ntagExtra={^R}Extra\r\ntagHidden= \r\n', encoding='utf-8-sig', newline='')
    # A legacy filter is deliberately not imported.
    (existing / 'tags_items.txt').write_text('tagHealthy={^G}Legacy Healthy\n', encoding='utf-8-sig')
    result = generate_consolidated_output(clean, tmp_path / 'output', _catalog(), BuildProfile('Health', {'health': 4}), existing_root=existing, host_relative_path=Path('tagsgdx3_uimain.txt'))
    raw = (tmp_path / 'output' / 'tagsgdx3_uimain.txt').read_bytes()
    text = raw.decode('utf-8-sig')
    assert '# Custom colors\r\n' in text
    assert 'tagExtra={^R}Extra\r\n' in text
    assert 'tagHidden= \r\n' in text
    assert 'tagDifficulty=Custom difficulty' in text
    assert 'tagMenu=Menu' in text
    assert 'tagHealthy=(C1)Healthy' in text
    assert 'Legacy Healthy' not in text and 'tagUnused' not in text
    assert result.files_written == 1 and not result.missing_affix_tags
    assert raw.startswith(b'\xef\xbb\xbf')
    assert len(list((tmp_path / 'output').rglob('*.txt'))) == 1


def test_reexport_refreshes_owned_names_and_removes_obsolete_grades_from_custom_entries(tmp_path):
    clean = _sources(tmp_path)
    existing = tmp_path / 'existing'
    existing.mkdir()
    master = existing / 'tagsgdx3_uimain.txt'
    master.write_text('tagHealthy={^G}Customized\n', encoding='utf-8-sig')
    one = tmp_path / 'one'
    generate_consolidated_output(clean, one, _catalog(), BuildProfile('Health', {'health': 4}), existing_root=existing, host_relative_path=Path(master.name))
    # Same output on repeat export: no stacked markers or growing sections.
    two = tmp_path / 'two'
    generate_consolidated_output(clean, two, _catalog(), BuildProfile('Health', {'health': 4}), existing_root=one, host_relative_path=Path(master.name))
    assert (one / master.name).read_bytes() == (two / master.name).read_bytes()
    (clean / master.name).write_text('tagDifficulty=Updated\ntagNewMenu=New\n', encoding='utf-8-sig')
    three = tmp_path / 'three'
    generate_consolidated_output(clean, three, AffixCatalog(()), BuildProfile(), existing_root=two, host_relative_path=Path(master.name))
    text = (three / master.name).read_text(encoding='utf-8-sig')
    assert 'tagHealthy={^G}Customized' in text
    assert '(C1)' not in text
    assert 'tagDifficulty=Updated' in text and 'tagNewMenu=New' in text
    assert 'tagMenu=' not in text
    assert text.count(BEGIN_BLOCK) == 1 and text.count(GRADE_HISTORY) == 1


def test_intentionally_hidden_graded_tag_remains_blank(tmp_path):
    clean = _sources(tmp_path)
    existing = tmp_path / 'existing'
    existing.mkdir()
    (existing / 'tagsgdx3_uimain.txt').write_text('tagHealthy= \n', encoding='utf-8-sig')
    result = generate_consolidated_output(clean, tmp_path / 'out', _catalog(), BuildProfile(), existing_root=existing, host_relative_path=Path('tagsgdx3_uimain.txt'))
    text = (tmp_path / 'out' / 'tagsgdx3_uimain.txt').read_text(encoding='utf-8-sig')
    assert 'tagHealthy= \n' in text
    assert result.annotated_lines == 0 and result.affix_tags_found == 1


def test_russian_host_keeps_every_grammatical_variant(tmp_path):
    clean = tmp_path / 'clean'
    host = Path('aom/tagsgdx1_achievements.txt')
    (clean / host.parent).mkdir(parents=True)
    (clean / host).write_text('tagAchievement=Достижение\n', encoding='utf-8-sig')
    (clean / 'tags_items.txt').write_text('tagHealthy=[ms]{^G}Здоровый[fs]{^G}Здоровая\n', encoding='utf-8-sig')
    result = generate_consolidated_output(clean, tmp_path / 'out', _catalog(), BuildProfile('Здоровье', {'health': 4}), host_relative_path=host, locale=RUSSIAN_LOCALE)
    text = (tmp_path / 'out' / host).read_text(encoding='utf-8-sig')
    assert '[ms]{^C}(C1){^G}Здоровый[fs]{^C}(C1){^G}Здоровая' in text
    assert 'tagAchievement=Достижение' in text
    assert result.master_relative_path == host


def test_missing_source_tags_are_reported_without_using_catalog_display_names(tmp_path):
    clean = _sources(tmp_path)
    (clean / 'tags_items.txt').write_text('tagOther=Other\n', encoding='utf-8-sig')
    result = generate_consolidated_output(clean, tmp_path / 'out', _catalog(), BuildProfile(), host_relative_path=Path('tagsgdx3_uimain.txt'))
    assert result.missing_affix_tags == ('tagHealthy',)
    assert 'tagHealthy=' not in (tmp_path / 'out' / 'tagsgdx3_uimain.txt').read_text(encoding='utf-8-sig')


def test_damaged_managed_section_never_overwrites_output(tmp_path):
    clean = _sources(tmp_path)
    existing = tmp_path / 'existing'
    existing.mkdir()
    (existing / 'tagsgdx3_uimain.txt').write_text(BEGIN_BLOCK + '\ntagHealthy=Broken\n', encoding='utf-8-sig')
    output = tmp_path / 'out'
    output.mkdir()
    sentinel = output / 'tagsgdx3_uimain.txt'
    sentinel.write_text('keep', encoding='utf-8')
    with pytest.raises(ValueError, match='unfinished'):
        generate_consolidated_output(clean, output, _catalog(), BuildProfile(), existing_root=existing, host_relative_path=Path(sentinel.name))
    assert sentinel.read_text() == 'keep'


def test_generation_replaces_old_staging_tree_with_only_the_master(tmp_path):
    clean = _sources(tmp_path)
    output = tmp_path / 'out'
    output.mkdir()
    (output / 'tags_items.txt').write_text('tagStale=Stale\n', encoding='utf-8')
    generate_consolidated_output(clean, output, _catalog(), BuildProfile(), host_relative_path=Path('tagsgdx3_uimain.txt'))
    assert [path.name for path in output.iterdir()] == ['tagsgdx3_uimain.txt']


def test_prepared_manifest_rejects_another_language(tmp_path):
    import json
    clean = _sources(tmp_path)
    (clean / 'localization-manifest.json').write_text(json.dumps({'locale': 'ru', 'host_relative_path': 'tagsgdx3_uimain.txt'}), encoding='utf-8')
    with pytest.raises(ValueError, match='language does not match'):
        generate_consolidated_output(clean, tmp_path / 'out', _catalog(), BuildProfile())
    assert not (tmp_path / 'out').exists()


def test_prepared_manifest_rejects_path_outside_source(tmp_path):
    import json
    clean = _sources(tmp_path)
    (clean / 'localization-manifest.json').write_text(json.dumps({'locale': 'en', 'host_relative_path': '../outside.txt'}), encoding='utf-8')
    with pytest.raises(ValueError, match='host path'):
        generate_consolidated_output(clean, tmp_path / 'out', _catalog(), BuildProfile())
