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

- Pro funkci **Export PDF** je potřeba doinstalovat `reportlab`:

```bash
pip install reportlab
```

## Základní kontrola

```bash
python -m unittest discover -s tests -v
```

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

## Další vhodný vývoj

1. záloha/obnova jedním tlačítkem i s exportem nastavení
2. silnější optimalizační jádro než `best-of-random`
3. jemnější model sousedství a vah
