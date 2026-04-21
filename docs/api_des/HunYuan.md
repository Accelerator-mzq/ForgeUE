```bash
//提交示例
curl -X POST 'https://tokenhub.tencentmaas.com/v1/api/image/submit' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "hy-image-v3.0",
    "prompt": "雨中, 竹林, 小路"
  }'

//查询示例
curl -X POST 'https://tokenhub.tencentmaas.com/v1/api/image/query' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "hy-image-v3.0",
    "id": "xxxxxxxxx"
  }'
  
  //提交示例
curl -X POST 'https://tokenhub.tencentmaas.com/v1/api/3d/submit' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "hy-3d-3.1",
    "prompt": "一只小狗"
  }'

//查询示例
curl -X POST 'https://tokenhub.tencentmaas.com/v1/api/3d/query' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "hy-3d-3.1",
    "id": "xxxxxx"
  }'
```

