# POI 2024 Mapping Notes

This note records the first-pass interpretation of the decompressed `POI 2024` CSV files.

## Useful Classified Files

- `交通设施服务.csv`
- `体育休闲服务.csv`
- `医疗保健服务.csv`
- `科教文化服务.csv`
- `购物服务.csv`
- `风景名胜.csv`

## Observed Category Signals

- Subway exits:
  - `midType = 地铁站`
  - `smallType = 出入口`
- Bus stops:
  - `midType = 公交车站`
  - `smallType = 公交车站相关`
- Schools:
  - `midType = 学校`
  - `smallType` includes `幼儿园`, `小学`, `中学`, `高等院校`
- Healthcare:
  - `bigType = 医疗保健服务`
  - `midType` includes `综合医院`, `专科医院`, `诊所`, `医疗保健服务场所`
- Pharmacies:
  - `smallType = 药房`
- Parks:
  - `midType = 公园广场`
  - `smallType = 公园`
- Groceries:
  - `midType` includes `便民商店/便利店`, `综合市场`, `超级市场`
  - `smallType` includes `便民商店/便利店`, `农副产品市场`, `超市`
- Fitness / sport:
  - `smallType` includes `健身中心`, `篮球场馆`, `游泳馆`, `综合体育馆`

## Caveat

Keyword matching on `name` is much noisier in 2024 than type-based filtering, especially for:

- `学校`
- `医院`
- `超市`
- `便利`

Those words often appear in nearby parking lots, bus stops, or access points rather than the
actual facility itself. The 2024 pipeline should therefore prefer `midType` and `smallType`
filters over `name` substring filters whenever possible.
