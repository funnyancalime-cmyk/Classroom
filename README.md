# Zasedací pořádek - lokální aplikace

Lokální desktopová aplikace v Pythonu/Tkinteru pro tvorbu zasedacího pořádku ve třídě.

## Co umí

- vytvořit třídu a automaticky jí vygenerovat mřížku míst
- přidávat a deaktivovat žáky
- ručně rozmisťovat žáky klikáním
- náhodně rozmístit žáky (`random` mód)
- najít výhodnější kombinaci z nasbíraných dat (`smart` mód: best-of-random + lokální výměny)
- uzamknout konkrétní usazení pro další generování
- po hodině ohodnotit celé rozesazení a jen vybrané žáky
- průběžně ukládat párové a poziční skóre do SQLite
- rozlišovat sousedství: vedle sebe / před-za / diagonálně
- zobrazit poslední rozesazení a znovu je načíst
- vypínat a zapínat konkrétní místa v učebně (uličky, kouty, laboratorní stoly)
- rozebrat skóre návrhu na konkrétní pozice a dvojice
- exportovat aktuální zasedací pořádek do PDF
- vytvořit zálohu lokální databáze a obnovit ji
- zobrazit přehled vazeb a pozic pro vybraného žáka (z historických dat)
- chránit aplikaci lokálním PINem a ručně ji zamknout
- archivovat (mazat) starou historii rozesazení podle stáří

## Ochrana dat

Aplikace ukládá jen minimum dat:

- název třídy
- jméno žáka
- plus/minus zkušenosti s konkrétním místem a sousedstvím
- celkové hodnocení rozesazení

Neukládá:

- diagnózy
- známky
- zdravotní údaje
- slovní poznámky o chování

Databáze je lokální soubor `seating_app.db` vedle aplikace.

## Spuštění

Vyžaduje Python 3.11+.

```bash
python app.py
```

Na Windows můžeš použít i `run_windows.bat`.

### Volitelné závislosti

- Pro funkci **Export PDF** je potřeba doinstalovat volitelné balíčky:

```bash
pip install -r requirements-optional.txt
```

## Základní kontrola

```bash
python -m unittest discover -s tests -v
```

Automaticky se stejné kontroly spouští i v GitHub Actions (`.github/workflows/ci.yml`) pro Python 3.11 a 3.12 (včetně GUI smoke přes `xvfb-run` s `--require-display`).

## Benchmark režimu smart

```bash
python scripts/benchmark_smart.py --rows 5 --cols 6 --students 26 --iterations 5
```

Profilace přes více scénářů:

```bash
python scripts/benchmark_matrix.py --seed 42 --repeats 3
```

Uložení výsledku do CSV:

```bash
python scripts/benchmark_matrix.py --seed 42 --repeats 3 --output benchmark-matrix.csv
```

Kontrola proti prahům:

```bash
python scripts/check_benchmark_regression.py --benchmark-csv benchmark-matrix.csv --thresholds benchmarks/thresholds.json --baseline-csv benchmarks/baseline_matrix.csv --max-regression-pct 40
```

Pro release postup použij `RELEASE_CHECKLIST.md`.

## GUI smoke test (volitelné)

```bash
python scripts/gui_smoke.py
```

Pozn.: Na Linuxu bez `DISPLAY` se test korektně přeskočí.

## Windows build (volitelné)

1) nainstaluj build závislosti:

```bash
pip install -r requirements-build.txt
```

2) spusť build script:

```bat
scripts\build_windows.bat
```

Výsledný soubor bude v `dist\SeatingOrder.exe`.

### Windows installer (Inno Setup, volitelné)

Po vygenerování `dist\SeatingOrder.exe` lze vytvořit installer:

```bat
scripts\build_installer_windows.bat
```

Skript očekává dostupný `iscc` (Inno Setup Compiler) v `PATH`.

Repo také obsahuje ručně spouštěný GitHub Actions workflow pro build `.exe` i installeru:
`.github/workflows/windows-build.yml` (`workflow_dispatch`).

## Ovládání

- běžný režim: vyber žáka vlevo a klikni na místo
- klik bez vybraného žáka: vyprázdní místo
- dvojklik na obsazené místo: zamkne / odemkne žáka pro další generování
- tlačítko **Upravit učebnu**: klikáním vypínáš a zapínáš místa
- tlačítko **Zapnout všechna místa**: rychlý návrat celé učebny do plně aktivního stavu
- panel **Proč tento návrh** ukazuje nejsilnější plusové a minusové vlivy
- **Export PDF** vytvoří tisknutelný přehled aktuálního rozesazení
- **Záloha DB** uloží kopii databáze jinam
- **Obnovit DB** vrátí stav aplikace z vybrané zálohy
- **Přehled žáka** zobrazí silné/negativní vazby se spolužáky a preferované pozice
- **Nastavení** otevře volitelné lokální zabezpečení (PIN) a další provozní volby
- **Archivace starých dat** smaže historická rozesazení starší než zvolený počet měsíců
- **Export/Import nastavení** uloží a obnoví `app_settings` ve formátu JSON

## Další vhodný vývoj

1. automatizované GUI testy (nad rámec checklist smoke testu)
2. hlubší profilace výkonu pro větší třídy (40+ žáků, víc běhů)
