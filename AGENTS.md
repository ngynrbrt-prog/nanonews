# NANONews projektutasítások

## Release notes

Minden új, a NANONews projekthez kapcsolódó felhasználói kéréshez készüljön külön Markdown release note a repó `Dokumentumok/releasenotes/` mappájában. Ez a szabály a kódot, a dokumentációt, az ütemezést és az egyéb projektfeladatokat érintő kérésekre is vonatkozik.

- Fájlnév: `vMAJOR.MINOR.PATCH-rovid-leiras.md`. A verziószám a dokumentum címében is szerepeljen.
- A következő verziót a mappában található legnagyobb verziószámból kell meghatározni. Hibajavítás, dokumentációs vagy egyéb kisebb kérés esetén növeld a PATCH értéket. Új, kompatibilis funkciónál növeld a MINOR értéket, kompatibilitást megszakító változásnál a MAJOR értéket. A kisebb komponenseket ekkor állítsd nullára.
- Rögzítsd a dátumot, a kérést, az eredményt és a tesztelés állapotát. Minden elvégzett ellenőrzésnél nevezd meg a módszert és a tényleges eredményt. Kihagyott vagy elakadt tesztnél add meg az okot. Dokumentációs feladatnál a fájl, a tartalom vagy a hivatkozások ellenőrzése is tesztként rögzíthető.
- A feladat lezárása előtt mentsd és ellenőrizd a release note-ot, majd linkeld a válaszban. A nyilvános repóban a kérést szükség esetén érzékeny adatok nélkül foglald össze.
