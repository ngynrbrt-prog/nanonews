# NANONews – rendszerterv

## Cél

Személyre szabott, naponta háromszor frissülő digitális újság. A weboldal a legfrissebb kiadást mutatja, az archívumban a korábbi kiadások időrendben visszanézhetők. A rovatválasztóval témára lehet szűrni; a menüpontok kis képernyőn is több sorba törnek.

## Ingyenes összetevők

- **GitHub Pages:** a statikus weboldal kiszolgálása.
- **GitHub Actions:** RSS-források lekérése, cikkoldalak nyilvános szövegének feldolgozása, kiadások archiválása és ütemezése.
- **Google Gemini API ingyenes kerete:** a hírek három hangnemű, rövid összefoglalójának elkészítése. Nincs fizetős tartalék; kvótakorlát vagy hiba esetén az elérhető RSS-kivonat jelenik meg.

A feldolgozás nem kerüli meg a fizetőfalat vagy a bejelentkezést. A generált szöveg saját, tömör összefoglaló; nem a teljes cikk másolata.

## Források és témák

Első körben: Telex, HVG, Index és Nemzeti Sport. A témák a `refresh_news.py` fájl `rules` listájában bővíthetők, a megjelenő rovatnevek az `index.html` fájl `topics` listájában vannak.

## Kiadások

A `.github/workflows/refresh.yml` ütemezése naponta 06:00, 14:00 és 20:00 Europe/Budapest szerint. A `refresh_news.py` frissíti a `data/latest.json` kiadást, és minden új kiadást a `data/archive/` alatt tárol.

## Gemini-kulcs biztonságos beállítása

A Gemini-kulcs **nem kerülhet ebbe a dokumentumba, a forráskódba vagy más, repóban tárolt fájlba**. A repó nyilvános, a commitolt kulcsot bárki kiolvashatná.

1. A Google AI Studio-ban hozz létre API-kulcsot az ingyenes használathoz. Olvasd át az ott megjelenő feltételeket, és csak akkor fogadd el a nyilatkozatokat, ha azok igazak rád.
2. GitHubon nyisd meg: **Settings → Secrets and variables → Actions → New repository secret**.
3. A név mező: `GEMINI_API_KEY`. A titkos érték mezőbe másold a kulcsot, majd mentsd el.
4. Kézi újragenerálás: **Actions → Refresh NANONews → Run workflow**. A kulcs a workflow futásakor titokként jut el a generáló kódhoz, és nem kerül bele az oldal fájljaiba.

Ha a kulcs valaha nyilvánosságra került, vond vissza a Google AI Studio-ban, majd hozz létre újat. Ne másold be a kulcsot csevegésbe vagy a repó dokumentumaiba.

## Stílusok

Minden hírhez a rendszer egy `tolkien` változatot tárol. A weboldal a Tolkien-hangulatú címet és részletes összefoglalót jeleníti meg. A változatok csak sikeres Gemini-hívás után kerülnek a kiadásba; a korábbi kiadások újrafeldolgozása kézi workflow-indítással történik.
