#!/bin/bash
COSTING_ENDPOINT="https://cds.climate.copernicus.eu/api/retrieve/v1/processes/derived-era5-single-levels-daily-statistics/costing?request_origin=ui"

curl -vL -X POST \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0" \
  -H "Accept: application/json, text/plain, */*" \
  -H "Accept-Language: en-US,en;q=0.5" \
  -H "Accept-Encoding: gzip, deflate, br, zstd" \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "Content-Length: 425" \
  -H "Origin: https://cds.climate.copernicus.eu" \
  -H "Sec-GPC: 1" \
  -H "Connection: keep-alive" \
  -H "Referer: https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics?tab=download" \
  -H "Sec-Fetch-Dest: empty" \
  -H "Sec-Fetch-Mode: cors" \
  -H "Sec-Fetch-Site: same-origin" \
  -d @costing_api.stac.json $COSTING_ENDPOINT
#   -H 'Cookie: intercom-device-id-cxqkdnoc=82d31ed1-9f24-4cfe-879b-654fa14562de; _ga_28RD493Z32=GS2.1.s1749578612$o3$g0$t1749578612$j60$l0$h0; _ga=GA1.1.1309255721.1749474542; _gcl_au=1.1.1640039821.1749474722.263140701.1749474724.1749474726; __Host-next-auth.csrf-token=479c4252c0709432b9b2bafc5ad9d459bd571db5a5cc0186aa429b0b29d84707%7Cf5d35170ccf333840cd938f98ad089a5cfd53f864a9478b66e41f86f877f66cd; __Secure-next-auth.callback-url=https%3A%2F%2Fcds.climate.copernicus.eu%2F' \

## RESULT: 
# {"id":"size","cost":12.0,"limit":400.0,"request_is_valid":false,"invalid_reason":"missing mandatory inputs"}