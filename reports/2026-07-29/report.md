# Mall Blotter Report

Generated **2026-07-29** · window **30 days** (since 2026-06-29) · **0** incidents (**0** violent) across 6 malls.

## Summary by mall

| Mall | Status | Total | VIOLENT | PROPERTY | QUALITY_OF_LIFE | OTHER | Nearest (m) | Most recent |
|---|---|---|---|---|---|---|---|---|
| Beverly Center | OK | 0 | 0 | 0 | 0 | 0 | - | - |
| Cherry Creek Shopping Center | FAILED ⚠️ | 0 | 0 | 0 | 0 | 0 | - | - |
| Lenox Square | FAILED ⚠️ | 0 | 0 | 0 | 0 | 0 | - | - |
| Northgate Station | FAILED ⚠️ | 0 | 0 | 0 | 0 | 0 | - | - |
| Opry Mills | FAILED ⚠️ | 0 | 0 | 0 | 0 | 0 | - | - |
| The Domain | FAILED ⚠️ | 0 | 0 | 0 | 0 | 0 | - | - |

## Data quality

- **Source failed** (THEDOMAIN / Austin PD Crime Reports): Socrata fetch failed for fdj4-gpfu: HTTP 400 for https://data.austintexas.gov/resource/fdj4-gpfu.json?%24where=latitude+between+30.39270168394081+and+30.410688116059188+AND+longitude+between+-97.73691453289148+and+-97.71606066710852+AND+occ_date+%3E+%272026-06-29T07%3A26%3A39%27&%24limit=5000&%24order=occ_date+DESC :: {"message":"Query coordinator error: query.soql.no-such-column; No such column: latitude; position: Map(row -> 1, column -> 325, line -> \"SELECT `incident_report_number`, `crime_type`, `ucr_code`, `family_violence`, `occ_date_time`, `occ_date`, `occ_time`, `rep_date_time`, `rep_date`, `rep_time`, `
- **Source failed** (OPRYMILLS / Metro Nashville PD Incidents): ArcGIS error for Metro Nashville PD Incidents: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ['Unable to perform query. Please check your parameters.']}
- **Source failed** (NORTHGATE / Seattle PD Crime Data): Socrata fetch failed for tazs-3rd5: HTTP 400 for https://data.seattle.gov/resource/tazs-3rd5.json?%24where=latitude%3A%3Anumber+between+47.69905138394081+and+47.71703781605919+AND+longitude%3A%3Anumber+between+-122.33973349064095+and+-122.31300410935904+AND+offense_date+%3E+%272026-06-29T07%3A26%3A39%27&%24limit=5000&%24order=offense_date+DESC :: {"message":"Query coordinator error: 400; ERROR: invalid input syntax for type numeric: \"REDACTED\"","errorCode":"400","data":{"source":"soql-server"}}
- **Source failed** (CHERRYCREEK / Denver PD Crime): ArcGIS error for Denver PD Crime: {'code': 400, 'message': 'Invalid URL', 'details': ['Invalid URL']}
- **Source failed** (LENOX / Atlanta PD Crime): ArcGIS error for Atlanta PD Crime: {'code': 400, 'message': 'Invalid URL', 'details': ['Invalid URL']}
