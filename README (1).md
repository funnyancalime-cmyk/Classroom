# Zasedací pořádek - lokální aplikace

Lokální desktopová aplikace v Pythonu/Tkinteru pro tvorbu zasedacího pořádku ve třídě.

## Co umí

- vytvořit třídu a automaticky jí vygenerovat mřížku míst
- přidávat a deaktivovat žáky
- ručně rozmisťovat žáky klikáním
- náhodně rozmístit žáky (`random` mód)
- najít výhodnější kombinaci z nasbíraných dat (`smart` mód)
- uzamknout konkrétní usazení pro další generování
- po hodině ohodnotit celé rozesazení a jen vybrané žáky
- průběžně ukládat párové a poziční skóre do SQLite
- zobrazit poslední rozesazení a znovu je načíst
- vypínat a zapínat konkrétní místa v učebně (uličky, kouty, laboratorní stoly)
- rozebrat skóre návrhu na konkrétní pozice a dvojice
- exportovat aktuální zasedací pořádek do PDF
- vytvořit zálohu lokální databáze a obnovit ji

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

## Další vhodný vývoj

1. lokální heslo k aplikaci
2. záloha/obnova jedním tlačítkem i s exportem nastavení
3. silnější optimalizační jádro než `best-of-random`
4. detailní přehled vztahů pro jednoho žáka
5. mazání nebo archivace starých dat po školním roce
