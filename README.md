# Zasedací pořádek – lokální MVP

Lokální desktopová aplikace v Pythonu/Tkinteru pro tvorbu zasedacího pořádku ve třídě.

## Co už umí

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

## Doporučený další vývoj

1. export do PDF
2. záloha databáze jedním klikem
3. lokální heslo
4. detailní přehled vztahů pro jednoho žáka
5. silnější optimalizační jádro než `best-of-random`
6. mazání nebo archivace starých dat po školním roce
