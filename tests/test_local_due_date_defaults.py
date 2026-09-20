from pathlib import Path


def test_all_classic_assignment_deadline_defaults_use_browser_local_date():
    source = Path("app_v924.py").read_text(encoding="utf-8")

    assert 'function localDueDate(days=7)' in source
    assert 'd.setDate(d.getDate()+Number(days||0))' in source
    assert 'd.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate())' in source

    assert source.count("localDueDate(7)") == 2
    assert source.count("localDueDate(3)") == 1

    assert "new Date(Date.now()+7*86400000).toISOString().slice(0,10)" not in source
    assert "new Date(Date.now()+3*86400000).toISOString().slice(0,10)" not in source
