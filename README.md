# NANONews
Személyes, magyar nyelvű hírújság. A GitHub Pages szolgálja ki az oldalt, a GitHub Actions gyűjti és archiválja a kiadásokat.

Források: Telex, HVG, Index, Nemzeti Sport és NBAnews.hu. Figyelt témák: Arsenal, Manchester City, Bayern München, Manchester United, Como, Premier League, F1, NBA, belföldi hírek (gazdaság, sport nélkül), belföldi parlament, belföldi tőzsde és külföldi tőzsde.

A részletes rendszerleírás a Dokumentumok/NANONews-mukodesi-leiras.md fájlban található. Minden további kérés és az ahhoz tartozó módosítás rögzítendő a dokumentum változásnaplójában.

## Kiadásrend

Az Action naponta 06:00, 14:00 és 20:00 órakor (Europe/Budapest) frissít. Az RSS-híreket, a cikkoldalak nyilvánosan elérhető szövegét és az archív kiadásokat a `data/` könyvtárban tárolja. Paywallt vagy belépést nem kerül meg.

## Stílusváltozatok aktiválása

Az eredeti cím és kivonat, valamint a Tolkien-hangú cím és részletes összefoglaló a Gemini API ingyenes kerete készíti el. A feldolgozás a teljes, nyilvánosan elérhető cikkből készít 3–5 mondatos, saját összefoglalót; nem másolja át a cikk teljes szövegét.

1. A Google AI Studio-ban hozz létre egy Gemini API-kulcsot, és ne kapcsold be a fizetős számlázást.
2. A GitHub-repóban nyisd meg: **Settings → Secrets and variables → Actions → New repository secret**.
3. A titok neve legyen `GEMINI_API_KEY`, az értéke pedig a kulcs.
4. Az automatikus frissítés a következő kiadástól megpróbálja elkészíteni és elmenteni a Tolkien-hangú változatot.

Ha a Gemini ingyenes kerete eléri a korlátot, vagy a forrásoldal nem adja vissza a cikk szövegét, az adott hír az elérhető RSS-kivonattal jelenik meg. A titkos kulcsot ne tedd a repó fájljaiba, és ne küldd el nyilvános üzenetben.

A GitHub Pages nyilvános repót használ; a cikkek és a NANONews-kiadások bárki számára elérhetők.
