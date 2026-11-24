# NANONews
Személyes, magyar nyelvű hírújság. A GitHub Pages szolgálja ki az oldalt, a GitHub Actions gyűjti és archiválja a kiadásokat.

Források: Telex, HVG, Nemzeti Sport, NBAnews.hu, Fűzővel kifelé!, 444.hu, Portfolio.hu és Origo.hu. Figyelt témák: Arsenal, Manchester City, Bayern München, Manchester United, Como, Premier League, F1, NBA, belföldi hírek (gazdaság, sport nélkül), belföldi parlament, belföldi tőzsde és külföldi tőzsde.

A részletes rendszerleírás a Dokumentumok/NANONews-mukodesi-leiras.md fájlban található. Minden további kérés és az ahhoz tartozó módosítás rögzítendő a dokumentum változásnaplójában.

A felület használatát a [NANONews felhasználói kézikönyv](Dokumentumok/NANONews-felhasznaloi-kezikonyv.md) mutatja be. A kézikönyvet minden felhasználót érintő változtatással együtt frissíteni kell.

## Kiadásrend

A hivatalos számok a 06:00–06:59-es és 17:00–17:59-es idősávban készülnek (Europe/Budapest). A GitHub Actions minden futáskor lekéri az RSS-listákat. A Portfolio.hu kivonatai a kiadások közötti futásokban készülnek, a többi forrásé legalább ötóránként. A háttérben mentett változatokat a következő kiadás felhasználja.

## Stílusváltozatok aktiválása

Az eredeti cím és kivonat, valamint a Tolkien-hangú cím és részletes összefoglaló a Gemini API ingyenes kerete készíti el. A feldolgozás a teljes, nyilvánosan elérhető cikkből készít 3–5 mondatos, saját összefoglalót; nem másolja át a cikk teljes szövegét.

1. A Google AI Studio-ban hozz létre egy Gemini API-kulcsot, és ne kapcsold be a fizetős számlázást.
2. A GitHub-repóban nyisd meg: **Settings → Secrets and variables → Actions → New repository secret**.
3. A titok neve legyen `GEMINI_API_KEY`, az értéke pedig a kulcs.
4. Az automatikus frissítés a következő kiadástól megpróbálja elkészíteni és elmenteni a Tolkien-hangú változatot.

Ha a Gemini ingyenes kerete eléri a korlátot, vagy a forrásoldal nem adja vissza a cikk szövegét, az adott hír az elérhető RSS-kivonattal jelenik meg. A titkos kulcsot ne tedd a repó fájljaiba, és ne küldd el nyilvános üzenetben.

A GitHub Pages nyilvános repót használ; a cikkek és a NANONews-kiadások bárki számára elérhetők.
