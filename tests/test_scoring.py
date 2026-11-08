from app.scoring import compute_points, is_correct, normalize, rank_of


def test_normalize_ignore_accents_casse_articles():
    assert normalize("  L'Océan   PACIFIQUE ! ") == "ocean pacifique"


def test_points_rapidite():
    assert compute_points(True, 20, 0) == 1000
    assert compute_points(True, 20, 10_000) == 750
    assert compute_points(True, 20, 20_000) == 500
    assert compute_points(True, 20, 99_000) == 500      # hors délai : plancher
    assert compute_points(False, 20, 0) == 0


def test_correction_qcm_et_libre():
    qcm = {"kind": "qcm", "correct": 2, "choices": ["a", "b", "c"], "accepted": []}
    assert is_correct(qcm, 2) and not is_correct(qcm, 1) and not is_correct(qcm, None) and not is_correct(qcm, "x")
    libre = {"kind": "libre", "correct": None, "choices": [], "accepted": ["La Seine"]}
    assert is_correct(libre, "seine") and is_correct(libre, "LA SEINE ") and not is_correct(libre, "loire")
    assert not is_correct(libre, "") and not is_correct(libre, 3)


def test_rang_ex_aequo():
    assert [rank_of(s, [300, 300, 100]) for s in (300, 300, 100)] == [1, 1, 3]
