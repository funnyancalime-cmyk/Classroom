# Postup vývoje a stav implementace

## Etapa 1 - lokální bezpečné MVP

- [x] čistě lokální úložiště v SQLite
- [x] minimální datový model bez citlivých údajů
- [x] vytvoření třídy a mřížky míst
- [x] správa seznamu žáků
- [x] ruční rozmisťování klikáním
- [x] `random` mód pro náhodné rozmístění
- [x] uzamykání konkrétních žáků na místa
- [x] ukládání historie rozesazení

## Etapa 2 - sběr zpětné vazby

- [x] hodnocení rozesazení jako celku (-2 až +2)
- [x] volitelné hodnocení jen některých žáků
- [x] ukládání párových bodů podle sousedství
- [x] ukládání pozičních bodů podle konkrétního místa
- [x] průběžné přepočítávání průměrného skóre a počtu pozorování

## Etapa 3 - doporučovací režim

- [x] základní skórovací funkce návrhu
- [x] `smart` mód přes best-of-random search
- [x] zohlednění uzamčených míst při generování
- [x] zobrazení aktuálního skóre návrhu

## Etapa 4 - reálnější provoz ve třídě

- [x] editor neaktivních míst / uliček přímo v plánku
- [x] rychlé zapnutí všech míst zpět
- [x] ignorování neaktivních míst při `random` i `smart` módu
- [x] detailní vysvětlení, proč byl návrh vybrán
- [x] rozpad skóre na pozice a sousedské vazby

## Etapa 5 - provozní jistota

- [x] export aktuálního zasedacího pořádku do PDF
- [x] záloha databáze jedním klikem
- [x] obnova databáze ze zálohy

## Etapa 6 - další vhodné kroky

- [x] lokální heslo k aplikaci
- [x] jemnější model sousedství a vah
- [x] silnější optimalizační jádro než best-of-random
- [x] filtr a přehled vztahů pro vybraného žáka
- [x] archivace / mazání starých dat podle období
