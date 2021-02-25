import json
import re
import scrapy
from urllib.parse import urlencode


CLIENT_ENDPOINT = 'https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1'
API_KEY_PATTERN = r'"apiKey"\:"([a-z0-9]+)"'


class TargetSpider(scrapy.Spider):
    name = 'target'

    def __init__(self, url, **kwargs):
        self.start_urls = [url]
        super().__init__(**kwargs)

    def get_pdp_client_url(self, api_key, tcin, store_id=1226):
        payload = {
            'key': api_key,
            'tcin': tcin,
            'store_id': store_id,
            'has_store_id': True,
            'pricing_store_id': store_id,
            'scheduled_delivery_store_id': 'none'
        }

        query_string = urlencode(payload)

        return f"{CLIENT_ENDPOINT}?{query_string}"

    def parse(self, response):
        script = response.css('script[type="application/ld+json"]::text').extract_first()

        data = json.loads(script)
        graph_data = data['@graph'][0]

        tcin = graph_data['sku']
        api_key = re.findall(API_KEY_PATTERN, response.text)[0]

        result = {
            'url': response.url,
            'tcin': tcin,
            'upc': graph_data['gtin13'],
            'price': '',
            'currency': graph_data['offers']['priceCurrency'],
            'title': response.css('h1[data-test="product-title"] > span::text').extract_first(),
            'description': graph_data['description'],
            'specs': {}
        }

        client_json_url = self.get_pdp_client_url(api_key, tcin)

        yield scrapy.Request(client_json_url, callback=self.parse_json_details, cb_kwargs={'result': result})

    def parse_json_details(self, response, result):
        data = json.loads(response.text)
        product_data = data['data']['product']

        try:
            me = next(child for child in product_data['children'] if child['tcin'] == result['tcin'])
            result['price'] = me['price']['current_retail']

            for bullet_item in me['item']['product_description']['bullet_descriptions']:
                tmp = bullet_item.split(':</B> ')
                name = tmp[0].replace('<B>', '')
                value = tmp[1]

                if name != 'Size':
                    result['specs'][name] = value
        except StopIteration:
            pass

        yield result

