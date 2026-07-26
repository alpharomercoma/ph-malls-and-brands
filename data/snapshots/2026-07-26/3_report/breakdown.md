# Mall directory scrape - breakdown (2026-07-26)

**328 properties · 42,412 listings · 12 chains**

Generated deterministically from the snapshot in `data/snapshots/2026-07-26/`. Regenerate with `mallscape report --date 2026-07-26`.

## Data quality

11,634 of 42,412 listings have no confidently mapped category.
501 normalized brand keys have multiple raw variants or require review.
Raw listings are retained; these signals describe uncertainty rather than removing rows.

## Chains

| chain      | properties |   malls |   listings | fetched    | source                                      |
|------------|-----------:|--------:|-----------:|------------|---------------------------------------------|
| araneta    |          4 |       4 |        319 | 2026-07-26 | aranetacity.com                             |
| ayala      |         32 |      32 |      5,640 | 2026-07-26 | api.ayalamalls.com                          |
| filinvest  |          5 |       5 |        956 | 2026-07-26 | filinvestlifemalls.com                      |
| fishermall |          2 |       2 |        342 | 2026-07-26 | fishermall.com.ph                           |
| gmall      |          6 |       6 |        944 | 2026-07-26 | gaisanomalls.com                            |
| megaworld  |         26 |      26 |      2,118 | 2026-07-26 | megaworld-lifestylemalls.com                |
| ortigas    |          4 |       4 |      1,279 | 2026-07-26 | ortigasmalls.com                            |
| robinsons  |         54 |      54 |      8,392 | 2026-07-26 | robinsonsmalls.com + vmd.robinsonsmalls.com |
| sm         |        126 |     100 |     19,640 | 2026-07-26 | smsupermalls.com                            |
| starmall   |          4 |       4 |        279 | 2026-07-26 | starmalls.com.ph                            |
| waltermart |         46 |      46 |      1,497 | 2026-07-26 | malls.waltermart.com.ph                     |
| xentro     |         19 |      19 |      1,006 | 2026-07-26 | xentromalls.com                             |
| **total**  |    **328** | **302** | **42,412** |            |                                             |

`properties` counts everything the operator publishes a directory for; `malls` excludes non-mall retail (condo podiums, amusement parks, office annexes). **Use `malls` for chain-vs-chain comparison.**

### Accuracy caveats

- **ayala** - Ayala's API returns duplicate `(mall, merchant)` pairs with distinct ids but no distinguishing fields, so listing counts run above the number of unique brands present.
- **waltermart** - **Counts are a FLOOR.** Every category page caps at 10 tenants and the mall page returns an identical set; no pagination or limit parameter lifts it. Malls with a capped category are truncated upstream.
- **xentro** - Some source list items merge two tenants into one line; those names are preserved verbatim rather than split on a guess.

## Properties

### araneta (4 properties, 319 listings)

| property       | region       | type | listings |
|----------------|--------------|------|---------:|
| Farmers Plaza  | metro-manila | mall |      100 |
| Ali Mall       | metro-manila | mall |       88 |
| Gateway Mall   | metro-manila | mall |       81 |
| Gateway Mall 2 | metro-manila | mall |       50 |

### ayala (32 properties, 5,640 listings)

| property                    | region       | type | listings |
|-----------------------------|--------------|------|---------:|
| Market! Market!             | metro-manila | mall |      478 |
| Glorietta                   | metro-manila | mall |      401 |
| Trinoma                     | metro-manila | mall |      386 |
| Ayala Center Cebu           | visayas      | mall |      383 |
| Ayala Malls Manila Bay      | metro-manila | mall |      341 |
| Abreeza                     | mindanao     | mall |      297 |
| Ayala Malls Capitol Central | visayas      | mall |      268 |
| U. P. Town Center           | metro-manila | mall |      256 |
| MarQuee Mall                | north-luzon  | mall |      238 |
| Greenbelt                   | metro-manila | mall |      229 |
| Ayala Malls Feliz           | metro-manila | mall |      226 |
| Centrio Mall                | mindanao     | mall |      214 |
| Ayala Malls Nuvali          | south-luzon  | mall |      210 |
| Ayala Malls Circuit         | metro-manila | mall |      188 |
| Ayala Malls Central Bloc    | visayas      | mall |      162 |
| Ayala Malls Vertis North    | metro-manila | mall |      151 |
| One Ayala                   | metro-manila | mall |      149 |
| Harbor Point                | north-luzon  | mall |      135 |
| Ayala Malls Cloverleaf      | metro-manila | mall |      129 |
| Ayala Malls Serin           | south-luzon  | mall |      106 |
| Ayala Malls The 30th        | metro-manila | mall |       92 |
| Ayala Malls Marikina        | metro-manila | mall |       81 |
| The District Imus           | south-luzon  | mall |       78 |
| Bonifacio High Street       | metro-manila | mall |       77 |
| Ayala Malls Legazpi         | south-luzon  | mall |       72 |
| Pavilion Mall               | south-luzon  | mall |       68 |
| Fairview Terraces           | metro-manila | mall |       53 |
| Metro Point Mall            | metro-manila | mall |       50 |
| One Bonifacio High Street   | metro-manila | mall |       45 |
| The District Dasmarinas     | south-luzon  | mall |       40 |
| Shops at Serendra           | metro-manila | mall |       37 |
| Ayala Malls Vermosa         | south-luzon  | mall |        0 |

### filinvest (5 properties, 956 listings)

| property                  | region       | type | listings |
|---------------------------|--------------|------|---------:|
| Festival Mall             | metro-manila | mall |      787 |
| Fora Mall                 | south-luzon  | mall |       65 |
| Main Square               | south-luzon  | mall |       58 |
| Filinvest Malls Dumaguete | visayas      | mall |       27 |
| IL Corso                  | visayas      | mall |       19 |

### fishermall (2 properties, 342 listings)

| property                  | region       | type | listings |
|---------------------------|--------------|------|---------:|
| Fisher Mall Quezon Avenue | metro-manila | mall |      195 |
| Fisher Mall Malabon       | metro-manila | mall |      147 |

### gmall (6 properties, 944 listings)

| property        | region   | type | listings |
|-----------------|----------|------|---------:|
| GMall of Davao  | mindanao | mall |      438 |
| GMall of Tagum  | mindanao | mall |      259 |
| GMall of Toril  | mindanao | mall |      139 |
| GMall of Digos  | mindanao | mall |      108 |
| Gmall of Cebu   | visayas  | mall |        0 |
| GMall of Gensan | mindanao | mall |        0 |

### megaworld (26 properties, 2,118 listings)

| property                          | region       | type | listings |
|-----------------------------------|--------------|------|---------:|
| Venice Grand Canal Mall           | metro-manila | mall |      301 |
| Uptown Mall                       | metro-manila | mall |      244 |
| Lucky Chinatown Mall              | metro-manila | mall |      201 |
| Newport City                      | metro-manila | mall |      163 |
| Eastwood Mall                     | metro-manila | mall |      156 |
| Festive Walk Mall                 | visayas      | mall |      153 |
| Southwoods Mall                   | south-luzon  | mall |      139 |
| Eastwood City Walk                | metro-manila | mall |       92 |
| Forbes Town                       | metro-manila | mall |       77 |
| Eastwood Cyber Mall               | metro-manila | mall |       65 |
| Lucky Chinatown - Prosperity Wing | metro-manila | mall |       56 |
| San Lorenzo Place Mall            | metro-manila | mall |       53 |
| California Garden Square          | metro-manila | mall |       45 |
| Festive Walk Parade               | visayas      | mall |       42 |
| Mactan Newtown                    | visayas      | mall |       42 |
| Uptown Parade                     | metro-manila | mall |       41 |
| Lucky Chinatown - Imperial Wing   | metro-manila | mall |       38 |
| McKinley West                     | metro-manila | mall |       38 |
| Alabang West Parade               | metro-manila | mall |       34 |
| Paseo Center                      | metro-manila | mall |       33 |
| The Greenhouse at Village Square  | metro-manila | mall |       32 |
| Arcovia City                      | metro-manila | mall |       29 |
| Twin Lakes                        | south-luzon  | mall |       16 |
| The Clubhouse at Temple Drive     | metro-manila | mall |       14 |
| Three Central Mall                | metro-manila | mall |       14 |
| Tuscany at McKinley Hill          | metro-manila | mall |        0 |

### ortigas (4 properties, 1,279 listings)

| property    | region       | type | listings |
|-------------|--------------|------|---------:|
| Greenhills  | metro-manila | mall |      903 |
| Estancia    | metro-manila | mall |      301 |
| Tiendesitas | metro-manila | mall |       39 |
| The Strip   | metro-manila | mall |       36 |

### robinsons (54 properties, 8,392 listings)

| property                      | region       | type | listings |
|-------------------------------|--------------|------|---------:|
| Robinsons Place Manila        | metro-manila | mall |      658 |
| Robinsons Magnolia            | metro-manila | mall |      405 |
| Robinsons Galleria            | metro-manila | mall |      404 |
| Robinsons Place Antipolo      | metro-manila | mall |      302 |
| Robinsons Novaliches          | metro-manila | mall |      287 |
| Robinsons Place Tacloban      | visayas      | mall |      241 |
| Robinsons Place Ilocos        | north-luzon  | mall |      235 |
| Robinsons Galleria South      | south-luzon  | mall |      231 |
| Robinsons Place Tuguegarao    | north-luzon  | mall |      228 |
| Robinsons Place Iligan        | mindanao     | mall |      225 |
| Robinsons Place Iloilo        | visayas      | mall |      207 |
| Robinsons Place Malolos       | north-luzon  | mall |      204 |
| Robinsons Place Dasmarinas    | south-luzon  | mall |      202 |
| Robinsons Place Imus          | south-luzon  | mall |      200 |
| Robinsons Metro East          | metro-manila | mall |      199 |
| Robinsons Place Palawan       | south-luzon  | mall |      198 |
| Robinsons Place Santiago      | north-luzon  | mall |      197 |
| Robinsons Galleria Cebu       | visayas      | mall |      185 |
| Robinsons Place Lipa          | south-luzon  | mall |      181 |
| Robinsons Place Dumaguete     | visayas      | mall |      180 |
| Robinsons Place Naga          | south-luzon  | mall |      173 |
| Robinsons Place Gen. Trias    | south-luzon  | mall |      161 |
| Robinsons Place Butuan        | mindanao     | mall |      159 |
| Robinsons Gapan               | north-luzon  | mall |      156 |
| Robinsons Starmills           | north-luzon  | mall |      150 |
| Robinsons Pagadian            | mindanao     | mall |      144 |
| Robinsons Place Pangasinan    | north-luzon  | mall |      143 |
| Robinsons Place Valencia      | mindanao     | mall |      139 |
| Robinsons Place La Union      | north-luzon  | mall |      133 |
| Robinsons North Tacloban      | visayas      | mall |      122 |
| Opus Mall                     | metro-manila | mall |      115 |
| Robinsons Place Tagum         | mindanao     | mall |      113 |
| Robinsons Cybergate Cebu      | visayas      | mall |      111 |
| Robinsons Place Bacolod       | visayas      | mall |      106 |
| Robinsons Place Las Pinas     | metro-manila | mall |      106 |
| Robinsons Place Ormoc         | visayas      | mall |      104 |
| Robinsons Sta. Rosa           | south-luzon  | mall |       98 |
| Robinsons Place Jaro          | visayas      | mall |       97 |
| Robinsons Place Roxas         | visayas      | mall |       92 |
| Robinsons Town Mall Malabon   | metro-manila | mall |       88 |
| Robinsons Place Antique       | visayas      | mall |       87 |
| Robinsons Place Pavia         | visayas      | mall |       84 |
| Robinsons Place GenSan        | mindanao     | mall |       75 |
| Robinsons Fuente              | visayas      | mall |       72 |
| Robinsons Angeles             | north-luzon  | mall |       64 |
| Robinsons Otis                | metro-manila | mall |       60 |
| Robinsons Cainta              | metro-manila | mall |       56 |
| Robinsons Cagayan de Oro      | mindanao     | mall |       49 |
| Robinsons Town Mall Los Banos | south-luzon  | mall |       49 |
| Robinsons Luisita             | north-luzon  | mall |       40 |
| Robinsons Tagaytay            | south-luzon  | mall |       34 |
| Robinsons Cybergate Davao     | mindanao     | mall |       24 |
| The Plaza Bagong Silang       | metro-manila | mall |       19 |
| Robinsons Cybergate Bacolod   | visayas      | mall |        0 |

### sm (126 properties, 19,640 listings)

| property                      | region       | type               | listings |
|-------------------------------|--------------|--------------------|---------:|
| SM City North Edsa            | metro-manila | mall               |      866 |
| SM City Fairview              | metro-manila | mall               |      739 |
| SM Megamall                   | metro-manila | mall               |      692 |
| SM Mall of Asia               | metro-manila | mall               |      686 |
| SM City Santa Rosa            | south-luzon  | mall               |      537 |
| SM City Pampanga              | north-luzon  | mall               |      516 |
| SM City Cebu                  | visayas      | mall               |      497 |
| SM City Clark                 | north-luzon  | mall               |      434 |
| SM Seaside City Cebu          | visayas      | mall               |      376 |
| SM City Dasmariñas            | south-luzon  | mall               |      361 |
| SM City Davao                 | mindanao     | mall               |      360 |
| SM City Baguio                | north-luzon  | mall               |      354 |
| SM City Iloilo                | visayas      | mall               |      352 |
| SM Southmall                  | metro-manila | mall               |      345 |
| SM City Bacolod               | visayas      | mall               |      330 |
| SM City Manila                | metro-manila | mall               |      314 |
| SM City Sucat                 | metro-manila | mall               |      298 |
| SM City Bicutan               | metro-manila | mall               |      290 |
| SM City San Lazaro            | metro-manila | mall               |      290 |
| SM City Bacoor                | south-luzon  | mall               |      276 |
| SM City Lipa                  | south-luzon  | mall               |      262 |
| SM City Cabanatuan            | north-luzon  | mall               |      259 |
| SM Lanang                     | mindanao     | mall               |      257 |
| SM City Marilao               | north-luzon  | mall               |      242 |
| SM City Grand Central         | metro-manila | mall               |      240 |
| SM City Batangas              | south-luzon  | mall               |      236 |
| SM CDO Downtown Premier       | mindanao     | mall               |      229 |
| SM City Baliwag               | north-luzon  | mall               |      228 |
| SM City Calamba               | south-luzon  | mall               |      228 |
| SM City Lucena                | south-luzon  | mall               |      221 |
| SM City Legazpi               | south-luzon  | mall               |      207 |
| SM Aura                       | metro-manila | mall               |      195 |
| SM City Sta. Mesa             | metro-manila | mall               |      191 |
| SM City General Santos        | mindanao     | mall               |      188 |
| SM City Tanza                 | south-luzon  | mall               |      187 |
| SM City Tuguegarao            | north-luzon  | mall               |      187 |
| SM City Olongapo Central      | north-luzon  | mall               |      185 |
| SM City Rosales               | north-luzon  | mall               |      184 |
| SM City Marikina              | metro-manila | mall               |      181 |
| SM City Molino                | south-luzon  | mall               |      179 |
| SM City Naga                  | south-luzon  | mall               |      172 |
| SM City Urdaneta Central      | north-luzon  | mall               |      172 |
| SM City Trece Martires        | south-luzon  | mall               |      170 |
| SM City San Pablo             | south-luzon  | mall               |      166 |
| SM City San Jose Del Monte    | north-luzon  | mall               |      163 |
| SM City Taytay                | metro-manila | mall               |      161 |
| The Podium                    | metro-manila | mall               |      161 |
| SM City Caloocan              | metro-manila | mall               |      160 |
| SM City Consolacion           | visayas      | mall               |      160 |
| SM City Cauayan               | north-luzon  | mall               |      158 |
| SM City Novaliches            | metro-manila | mall               |      158 |
| SM City Sorsogon              | south-luzon  | mall               |      156 |
| SM City Butuan                | mindanao     | mall               |      152 |
| SM City Tarlac                | north-luzon  | mall               |      152 |
| SM City Valenzuela            | metro-manila | mall               |      149 |
| SM City Bataan                | north-luzon  | mall               |      145 |
| SM City Masinag               | metro-manila | mall               |      145 |
| SM City Laoag                 | north-luzon  | mall               |      144 |
| SM City San Mateo             | metro-manila | mall               |      144 |
| SM City Sto. Tomas            | south-luzon  | mall               |      144 |
| SM City CDO Uptown            | mindanao     | mall               |      140 |
| SM City East Ortigas          | metro-manila | mall               |      139 |
| SM City Puerto Princesa       | south-luzon  | mall               |      137 |
| SM Center Lemery              | south-luzon  | mall               |      132 |
| SM City Mindpro               | mindanao     | mall               |      128 |
| SM City Telabastagan          | north-luzon  | mall               |      127 |
| SM City Roxas                 | visayas      | mall               |      122 |
| SM Center Dagupan             | north-luzon  | mall               |      114 |
| SM City Daet                  | south-luzon  | mall               |      114 |
| SM City Rosario               | south-luzon  | mall               |      113 |
| SM City BF Parañaque          | metro-manila | mall               |      110 |
| SM J Mall                     | visayas      | mall               |      108 |
| SM Center Pulilan             | north-luzon  | mall               |      107 |
| SM Center Angono              | metro-manila | mall               |      102 |
| SM Center Las Piñas           | metro-manila | mall               |      100 |
| SM Center Tuguegarao Downtown | north-luzon  | mall               |      100 |
| S Maison                      | metro-manila | mall               |       99 |
| SM Center Ormoc               | visayas      | mall               |       98 |
| SM Center Pasig               | metro-manila | mall               |       91 |
| SM Center San Pedro           | south-luzon  | mall               |       86 |
| SM Center Muntinlupa          | metro-manila | mall               |       74 |
| SM City Olongapo Downtown     | north-luzon  | mall               |       71 |
| SM Center Sangandaan          | north-luzon  | mall               |       68 |
| SM Center Imus                | south-luzon  | mall               |       67 |
| SM Megacenter Cabanatuan      | north-luzon  | mall               |       61 |
| SM City San Fernando Downtown | north-luzon  | mall               |       56 |
| SMDC Light Mall               | metro-manila | residential-retail |       46 |
| SM Savemore Tacloban          | visayas      | mall               |       40 |
| SM By the Bay                 | metro-manila | mall               |       39 |
| SM Center Antipolo Downtown   | metro-manila | mall               |       38 |
| SMDC Jazz Mall                | metro-manila | residential-retail |       38 |
| SM Center Shaw                | metro-manila | mall               |       37 |
| MOA Square                    | metro-manila | mall               |       30 |
| SMDC Mplace Mall              | metro-manila | residential-retail |       28 |
| SM Center Congressional       | metro-manila | mall               |       25 |
| SMDC Strip at Mezza           | metro-manila | residential-retail |       25 |
| SMDC Sun Mall                 | metro-manila | residential-retail |       24 |
| SM Savemore Apalit            | north-luzon  | mall               |       23 |
| SMDC Air Mall                 | metro-manila | residential-retail |       23 |
| SMDC Fame Mall                | metro-manila | residential-retail |       23 |
| SMDC Grace Mall               | metro-manila | residential-retail |       23 |
| SM Savemore Nagtahan          | metro-manila | mall               |       21 |
| SMDC Strip at Grass           | metro-manila | residential-retail |       17 |
| SM Hypermarket Sucat Lopez    | metro-manila | mall               |       16 |
| SM Marketmall Dasmarinas      | south-luzon  | mall               |       16 |
| SMDC Strip at Sea             | metro-manila | residential-retail |       15 |
| SMDC Strip at Shore           | metro-manila | residential-retail |       15 |
| SM Hypermarket Lapu-Lapu      | visayas      | mall               |       13 |
| SMDC Breeze Mall              | metro-manila | residential-retail |       11 |
| NU MALL OF ASIA BUILDING      | metro-manila | office-annex       |        9 |
| Wind Residences               | south-luzon  | residential-retail |        8 |
| Mall Of Asia Arena Annex Bldg | metro-manila | office-annex       |        7 |
| SMDC Strip at Trees           | metro-manila | residential-retail |        7 |
| SMDC Green Mall               | metro-manila | residential-retail |        6 |
| SMDC Strip at Blue            | metro-manila | residential-retail |        5 |
| SMDC Strip at Shell           | metro-manila | residential-retail |        5 |
| SMDC Strip at Princeton       | metro-manila | residential-retail |        4 |
| SMDC Strip at Berkeley        | metro-manila | residential-retail |        2 |
| SMDC Strip at Shine           | metro-manila | residential-retail |        2 |
| Sky Ranch Baguio              | north-luzon  | amusement-park     |        1 |
| Sky Ranch Pampanga            | north-luzon  | amusement-park     |        1 |
| Sky Ranch Tagaytay            | south-luzon  | amusement-park     |        1 |
| SMBY Amusement Park           | nan          | amusement-park     |        1 |
| SM City La Union              | north-luzon  | mall               |        0 |
| SM City Zamboanga             | mindanao     | mall               |        0 |
| SM Makati                     | metro-manila | mall               |        0 |

### starmall (4 properties, 279 listings)

| property                    | region       | type | listings |
|-----------------------------|--------------|------|---------:|
| Starmall Alabang            | metro-manila | mall |      107 |
| Starmall San Jose del Monte | north-luzon  | mall |       98 |
| Starmall EDSA-Shaw          | metro-manila | mall |       64 |
| Starmall Talisay Cebu       | visayas      | mall |       10 |

### waltermart (46 properties, 1,497 listings)

| property                     | region       | type | listings |
|------------------------------|--------------|------|---------:|
| WalterMart Dasmariñas        | south-luzon  | mall |       49 |
| WalterMart Makati            | metro-manila | mall |       47 |
| WalterMart Sta. Maria        | north-luzon  | mall |       46 |
| WalterMart Gapan             | north-luzon  | mall |       45 |
| WalterMart North EDSA        | metro-manila | mall |       45 |
| WalterMart Sucat             | metro-manila | mall |       44 |
| WalterMart Antipolo          | metro-manila | mall |       43 |
| WalterMart Bacoor            | south-luzon  | mall |       42 |
| WalterMart Bicutan           | metro-manila | mall |       42 |
| WalterMart Balayan           | south-luzon  | mall |       41 |
| WalterMart E.Rodriguez       | metro-manila | mall |       41 |
| WalterMart Guiguinto         | north-luzon  | mall |       41 |
| WalterMart Subic             | north-luzon  | mall |       41 |
| WalterMart Concepcion        | north-luzon  | mall |       39 |
| WalterMart Paniqui           | north-luzon  | mall |       39 |
| WalterMart Plaridel          | north-luzon  | mall |       39 |
| WalterMart San Fernando      | north-luzon  | mall |       39 |
| WalterMart Sta. Rosa         | south-luzon  | mall |       38 |
| WalterMart Taytay            | metro-manila | mall |       38 |
| WalterMart Nasugbu           | south-luzon  | mall |       37 |
| WalterMart Balanga           | north-luzon  | mall |       35 |
| WalterMart Baliwag           | north-luzon  | mall |       34 |
| WalterMart General Trias     | south-luzon  | mall |       34 |
| WalterMart Naic              | south-luzon  | mall |       34 |
| WalterMart Tanauan           | south-luzon  | mall |       34 |
| WalterMart Arayat            | north-luzon  | mall |       33 |
| WalterMart Malolos           | north-luzon  | mall |       33 |
| WalterMart San Jose          | north-luzon  | mall |       33 |
| WalterMart Caloocan          | metro-manila | mall |       32 |
| WalterMart Makiling          | south-luzon  | mall |       32 |
| WalterMart Muntinlupa        | metro-manila | mall |       32 |
| WalterMart Pasay             | metro-manila | mall |       32 |
| WalterMart Trece Martires    | south-luzon  | mall |       31 |
| WalterMart Macapagal         | metro-manila | mall |       30 |
| WalterMart Cabanatuan        | north-luzon  | mall |       29 |
| WalterMart Capas             | north-luzon  | mall |       27 |
| WalterMart Candelaria        | south-luzon  | mall |       26 |
| WalterMart The Junction      | metro-manila | mall |       23 |
| WalterMart Batangas City     | south-luzon  | mall |       22 |
| WalterMart Cabuyao           | south-luzon  | mall |       22 |
| WalterMart Carmona           | south-luzon  | mall |       21 |
| WalterMart Sta. Rosa Bel-Air | south-luzon  | mall |       17 |
| WalterMart Talavera          | north-luzon  | mall |       15 |
| WalterMart Mabalacat         | north-luzon  | mall |        0 |
| WalterMart San Pascual       | south-luzon  | mall |        0 |
| WalterMart Silang            | south-luzon  | mall |        0 |

### xentro (19 properties, 1,006 listings)

| property                 | region       | type | listings |
|--------------------------|--------------|------|---------:|
| Montalban Town Center    | metro-manila | mall |      167 |
| Balagtas Town Center     | north-luzon  | mall |      102 |
| XentroMall Calapan       | south-luzon  | mall |       79 |
| XentroMall Santiago      | north-luzon  | mall |       78 |
| XentroMall Lemery        | south-luzon  | mall |       68 |
| Tanay Town Center        | south-luzon  | mall |       67 |
| XentroMall Roxas         | north-luzon  | mall |       66 |
| Mall Of The Valley       | north-luzon  | mall |       64 |
| Ab Central               | metro-manila | mall |       55 |
| Northstar Mall           | north-luzon  | mall |       46 |
| Morong Centerpoint       | metro-manila | mall |       41 |
| XentroMall Tumauini      | north-luzon  | mall |       41 |
| Sta Ana Public Market    | metro-manila | mall |       37 |
| XentroMall Cabagan       | north-luzon  | mall |       32 |
| Shopking                 | metro-manila | mall |       27 |
| Ilagan City Mall Isabela | north-luzon  | mall |       19 |
| XentroMall San Andres    | metro-manila | mall |       17 |
| XentroMall Antipolo      | metro-manila | mall |        0 |
| XentroMall Polangui      | south-luzon  | mall |        0 |

## Properties with zero listings

13 properties publish no tenant directory. Every one was checked against its source and is an upstream gap, not a parse failure.

| chain      | property                    | id                       |
|------------|-----------------------------|--------------------------|
| ayala      | Ayala Malls Vermosa         | ayala-vermosa            |
| gmall      | Gmall of Cebu               | gmall-of-cebu            |
| gmall      | GMall of Gensan             | gmall-of-gensan          |
| megaworld  | Tuscany at McKinley Hill    | tuscany-at-mckinley-hill |
| robinsons  | Robinsons Cybergate Bacolod | cybergate-bacolod        |
| sm         | SM City La Union            | sm-city-la-union         |
| sm         | SM City Zamboanga           | sm-city-zamboanga        |
| sm         | SM Makati                   | sm-makati                |
| waltermart | WalterMart Mabalacat        | mabalacat                |
| waltermart | WalterMart San Pascual      | san-pascual              |
| waltermart | WalterMart Silang           | silang                   |
| xentro     | XentroMall Antipolo         | xentro-mall-antipolo     |
| xentro     | XentroMall Polangui         | xentro-mall-polangui     |

## Excluded operators

Operators investigated but not scraped. Each entry records the finding and what would have to change for a scraper to become viable.

| operator                            | malls | status                     |
|-------------------------------------|------:|----------------------------|
| CityMall (DoubleDragon)             |    43 | no-tenant-directory        |
| Gaisano Capital Group               |     - | blocked-not-verified       |
| Gaisano Grand Malls                 |    46 | no-tenant-directory        |
| LCC Group (Bicol)                   |     - | blocked-not-verified       |
| LTS Malls                           |     - | not-located                |
| NCCC Malls                          |     9 | likely-no-tenant-directory |
| Primark Town Centers (LKY Group)    |    45 | no-tenant-directory        |
| Puregold Price Club                 |     - | out-of-scope-shape         |
| Shangri-La Plaza (Shang Properties) |     1 | no-current-directory       |
| Vista Malls (Vista Land)            |    20 | no-tenant-directory        |

**CityMall (DoubleDragon)** - citymall.com.ph is a thin DoubleDragon corporate shell; /citymall_map returns a 423-byte stub. DoubleDragon reported 43 operating CityMalls at end-2024 with a target of 100 by 2030. These are small community malls anchored by a supermarket; no per-mall tenant directory is published on any official domain found.

**Gaisano Capital Group** - NOT VERIFIED. Site returns HTTP 403 to scripted requests. Whether a tenant directory exists behind it is unknown.

**Gaisano Grand Malls** - VERIFIED. WordPress; branches are ordinary posts (slug gaisano-grand-mall-<place>) reachable via /wp-json/wp/v2/posts and a paginated /branches/ listing. Each branch post contains only ADDRESS, MALL HOURS (supermarket + department store) and PHONE NUMBER — no tenant list. These are department-store/supermarket-anchored retail centres, not tenant-leased malls.

**LCC Group (Bicol)** - NOT VERIFIED. Serves a 4.6KB 'Redirecting...' bot-challenge shell to scripted requests (same WAF pattern as XentroMall's parked domain and Shangri-La's).

**LTS Malls** - NOT VERIFIED. No official domain located; ltsmalls.com does not resolve. Search results conflate it with NCCC. Operator identity needs confirming before scraping.

**NCCC Malls** - PARTIALLY VERIFIED. nccc.com.ph/business-unit/nccc-malls/ is a corporate business-unit page (company profile, vision/mission, press) with no tenant listing found. ~9 branches across Davao, Tagum and Palawan per their own copy. No per-mall directory URL located.

**Primark Town Centers (LKY Group)** - ~45 provincial community centers exposed as WordPress pages named location-<place> (plus location-luzon-malls / -visayas-malls / -mindanao-malls index pages). Each page carries only a street address and leasing contact — no tenant list. Mall list IS obtainable from the WP REST API.

**Puregold Price Club** - NOT a mall operator in this dataset's sense: each Puregold branch is a single supermarket/hypermarket, not a leased mall with a tenant roster. Adding ~400 branches would inject 400 'malls' each holding one 'tenant' (itself) and would badly skew brand-presence and mall-size analysis. /store-locator/ 404s; the correct locator path was not found before running out of budget.

**Shangri-La Plaza (Shang Properties)** - Their official domain shangrila-plaza.com no longer resolves (no DNS), and shangrilaplaza.com.ph is a ParkLogic parked page offering the domain for sale. The only surviving official store listing is a Google Sites page at sites.google.com/view/shangcommunity/store-listing, which is explicitly stamped 'Updated as of February 02, 2021' — COVID-era data, five years stale. NOT scraped: importing 2021 tenants into a 2026 snapshot would silently corrupt month-over-month brand analysis.

**Vista Malls (Vista Land)** - WordPress site with a page per mall and a /stores/<slug>/ route, but the store sections render only logo carousels — no tenant names in the markup. The dev mirror (dev.vistamalls.com.ph/<mall>/store/) still contains Lorem ipsum placeholders, so the directory was never populated. Mall list IS obtainable from the WP REST API (/wp-json/wp/v2/pages).

## Known gaps inside scraped chains

### araneta

| property                    | region       | opened | type          |
|-----------------------------|--------------|--------|---------------|
| Cyberpark Tower 1           | metro-manila | -      | office-retail |
| Cyberpark Tower 2           | metro-manila | -      | office-retail |
| Farmers Market              | metro-manila | -      | public-market |
| Fiesta Carnival Arcade      | metro-manila | -      | arcade-retail |
| Gateway Tower Shops         | metro-manila | -      | office-retail |
| New Frontier Theater Arcade | metro-manila | -      | arcade-retail |
| Shopwise Araneta City       | metro-manila | -      | supermarket   |

### ayala

| property                         | region       | opened     | type            |
|----------------------------------|--------------|------------|-----------------|
| Ayala Malls Arca South           | metro-manila | 2026-02-13 | mall            |
| Ayala Malls Evo City             | south-luzon  | 2025-09-05 | mall            |
| Ayala Malls Gatewalk             | visayas      | 2026-12-16 | mall            |
| Ayala Malls Parklinks            | metro-manila | -          | mall            |
| Azuela High Street               | mindanao     | 2024-10    | lifestyle-strip |
| Garden Bloc at Cebu IT Park      | visayas      | 2015       | lifestyle-strip |
| Seagrove                         | visayas      | 2024-01    | lifestyle-strip |
| Shops at Ayala North Exchange    | metro-manila | 2019-12    | lifestyle-strip |
| The District North Point         | visayas      | 2013-04-03 | mall            |
| The Link Car Park                | metro-manila | 2010       | carpark-retail  |
| The Shops Ayala Triangle Gardens | metro-manila | 2022       | lifestyle-strip |
| The Shops at Atria               | visayas      | 2015       | lifestyle-strip |
| The Shops at Azuela Cove         | mindanao     | 2021       | lifestyle-strip |
| The Walk at Cebu IT Park         | visayas      | 2008       | lifestyle-strip |

### robinsons

| property                           | region       | opened | type           |
|------------------------------------|--------------|--------|----------------|
| Robinsons Bulacan Town Center      | north-luzon  | 2027   | mall           |
| Robinsons Townville BF Paranaque   | metro-manila | -      | community-mall |
| Robinsons Townville Buhay na Tubig | south-luzon  | -      | community-mall |
| Robinsons Townville Cabanatuan     | north-luzon  | 2008   | community-mall |
| Robinsons Townville Meycauayan     | north-luzon  | -      | community-mall |
| Robinsons Townville Perdices       | visayas      | -      | community-mall |
| Robinsons Townville Pulilan        | north-luzon  | 2010   | community-mall |
| Robinsons Townville Regalado       | metro-manila | -      | community-mall |
| The Jewel                          | metro-manila | 2027   | mall           |
| The Mall @ NUSTAR                  | visayas      | 2022   | luxury-mall    |

## Brand reach

11,489 distinct brands after normalization.

| brand                  | malls | chains |
|------------------------|------:|-------:|
| WATSONS                |   197 |     12 |
| POTATO CORNER          |   195 |     11 |
| BENCH                  |   176 |     12 |
| BANCO DE ORO           |   173 |     10 |
| JOLLIBEE               |   173 |     11 |
| SAMSUNG                |   169 |     10 |
| PENSHOPPE              |   163 |     12 |
| EXECUTIVE OPTICAL      |   154 |     11 |
| VIVO                   |   144 |     10 |
| AFICIONADO             |   136 |     10 |
| FAMOUS BELGIAN WAFFLES |   131 |      5 |
| OPPO                   |   131 |     11 |
| KFC                    |   130 |      8 |
| NATIONAL BOOKSTORE     |   130 |     10 |
| KETTLE KORN            |   129 |      9 |
| MANG INASAL            |   128 |     11 |
| IAN DARCY              |   127 |      8 |
| CHOWKING               |   123 |     10 |
| DUNKIN                 |   118 |      5 |
| GREENWICH              |   118 |      9 |
