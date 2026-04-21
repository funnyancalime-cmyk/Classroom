# Release checklist (lokální desktop verze)

## 1) Automatické kontroly

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m py_compile app.py`
- [ ] `python scripts/gui_smoke.py`
- [ ] (volitelně) `python scripts/benchmark_matrix.py --seed 42 --repeats 3 --output benchmark-matrix.csv`
- [ ] (volitelně) `python scripts/check_benchmark_regression.py --benchmark-csv benchmark-matrix.csv --thresholds benchmarks/thresholds.json --baseline-csv benchmarks/baseline_matrix.csv --max-regression-pct 40`

## 2) Ruční smoke test (GUI)

- [ ] vytvoření nové třídy, přidání žáků, ruční rozmístění
- [ ] `random` + `smart` generování
- [ ] uzamknutí míst + opětovné generování
- [ ] hodnocení hodiny a kontrola, že se projeví ve skóre
- [ ] přehled žáka (pair/seat data)
- [ ] export PDF (pokud je nainstalovaný `reportlab`)
- [ ] záloha DB + obnova DB
- [ ] nastavení PIN + zamknutí/odemknutí
- [ ] archivace starých dat
- [ ] export/import nastavení JSON

## 3) Kontrola artefaktů

- [ ] (volitelně) Windows build: `scripts\\build_windows.bat`
- [ ] (volitelně) Windows installer: `scripts\\build_installer_windows.bat`
- [ ] (volitelně) cloud build: GitHub Actions `windows-build.yml` (exe + installer)
- [ ] README a ROADMAP odpovídají aktuálním funkcím
- [ ] není přidaný `seating_app.db` ani jiné lokální/temporární soubory
- [ ] release commit obsahuje jen zamýšlené změny (`git status`, `git show --stat`)
