# coding:utf-8
# author:alex lin

import re
import uuid

import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from sinahouse.items import SinaHouseItem
from sinahouse import settings


class SinaHouseSpider(CrawlSpider):
    """新浪房产爬虫: http://sh.house.sina.com.cn/"""
    name = 'sinahouse'
    allowed_domains = ['house.sina.com.cn']
    start_urls = ['http://data.house.sina.com.cn/sc/search/?keyword=&charset=utf8',]
    rules = [
            Rule(LinkExtractor(allow = ('.*\.cn/\w+\d+/#wt_source.*?bt.*')),callback='parse_item',follow=False), #具体楼盘链接提取
            Rule(LinkExtractor(allow = ('^http://data.house.sina.com.cn/\w+/search$')),process_links="parse_city_links"), #各个城市链接提取
            Rule(LinkExtractor(allow = ('^http://data.house.sina.com.cn/\w+/search/\?bcity.*'))), #各个省份下有其他城市的链接提取
            Rule(LinkExtractor(allow = ('/\w+/search-\d*/.*'))), #下一页链接
 
            ]

#    下一页链接url提取出来实际是相对路径,LinkExtractor自动补全了url路径 故省略
#     ,process_links="parse_city_next_links"
#     def parse_city_next_links(self,links):
#         for link in links:
#             link.url = "http://data.house.sina.com.cn" + link.url
#         return links

    # 当时网站提取出的链接,直接跟进,会报服务器错误(网站自身原因,估计某个程序员该扣绩效了,哈哈),追加后缀就可以正常打开
    def parse_city_links(self,links):
        for link in links:
            link.url = link.url +'?keyword=&charset=utf8'
        return links
        
    def parse_item(self,response):
        """提取楼盘信息详情"""
        item = SinaHouseItem()
        item['source_id'] = settings.SOURCE
        item['save_path'] = settings.IMAGE_PATH
        item['community_name'] = response.xpath('//h1/text()').extract_first()
        item['index_url'] = response.url
        item['open_date'] = '-'.join(re.findall('(\d+)',response.xpath(u"//*[@id='callmeBtn']/ul/li[4]/span[2]/text()").extract_first(default=u'待定').strip()))
        item['check_in_date'] = '-'.join(re.findall('(\d+)',response.xpath(u'(//*[@id="callmeBtn"]//div[@title])[2]/@title').extract_first(default=u'待定')))
        item['developer'] = response.xpath(u"//div[@class='info wm']/ul/li[3]/text()").extract_first(default=u'未知').strip()
        item['property_manage_com'] = response.xpath(u"//li[contains(span,'物业公司')]/text()").extract_first(default=u'未知').strip()
        item['address'] = response.xpath(u'//*[@id="callmeBtn"]/ul/li[2]/span[2]/text()').extract_first(default=u'未知').strip()
        item['area_name'] = response.xpath("//span[@class='fl']/a[3]//text()").extract_first(default=u'未知').strip()
        item['city_name'] = response.xpath("//span[@class='fl']/a[1]//text()").extract_first(default=u'未知').replace(u'房产','').strip()
        item['cover_url'] = [response.xpath("//*[@id='con_tab1_con_4']/a/img/@lsrc").extract_first(),str(uuid.uuid4()).replace('-','')]
        item['household_size'] = response.xpath("//div[@class='info wm']/ul/li[5]/text()").extract_first(default=u'未知').replace(u'户','').strip()
        item['property_manage_fee'] = response.xpath("//div[@class='info wm']/ul/li[7]/text()").extract_first(default=u'未知').strip()
        item['construction_area'] = response.xpath("//div[@class='info wm']/ul/li[9]/text()").extract_first(default=u'未知').strip()
        item['property_type'] = response.xpath("//div[@class='info wm']/ul/li[6]/text()").extract_first(default=u'未知').strip()
        item['decoration'] = response.xpath("//div[@class='info wm']/ul/li[12]/text()").extract_first(default=u'未知').strip()
        item['per_square_price'] = response.xpath("//*[@id='callmeBtn']/ul/li[1]/em[1]/text()").extract_first(default=u'未知').strip()
        item['longtitude_latitude'] = ','.join([response.xpath('//script').re_first(".*?coordx='(\d+.\d+)'"), response.xpath('//script').re_first(".*?coordy='(\d+.\d+)'.*")])
        #楼盘户型图首页
        image_index_url = response.xpath('/html/body/div[1]/div[10]/ul/li[4]/a/@href').extract_first()

#         from scrapy.shell import inspect_response
#         inspect_response(response, self)
        if image_index_url:
            yield scrapy.Request(url=image_index_url, meta={"house_item": item}, callback=self.parse_item_image)
        else:
            self.logger.info(u'此楼盘无图片:' + item['index_url'])
            yield item
    
    def parse_item_image(self,response):
        """楼盘户型图处理"""
        item = response.meta["house_item"]
        item['house_img_urls'] = []
        huxing_index_url = response.xpath(u"//div[@class='housingNav w']//li[contains(a,'户型图')]/a/@href").extract_first()
        if huxing_index_url:
            self.logger.debug(u'楼盘图片首页:' + huxing_index_url )
            yield scrapy.Request(url = huxing_index_url,meta={'house_item':item},callback=self.parse_item_huxing)
        else:
            self.logger.info(u'此楼盘无户型图片:' + item['index_url'])
            yield item
            
    def parse_item_huxing(self,response):
        """户型图处理"""
        item = response.meta['house_item']
        lis = response.xpath("//ul[@class='sFy03 clearfix']//li")
        for li in lis:
            huxing = li.xpath(".//div[@class='imgBox']/p/text()").extract_first(default=u'其他')
            img_src_url_tmp = li.xpath('.//img/@src').extract_first()
            # 转换为大图的链接
            img_src_url = img_src_url_tmp[:(img_src_url_tmp.index('mk7')+3)]+'.jpg'
            size = li.xpath("./p[1]/em/text()").extract_first(default=0)
            item['house_img_urls'].append([str(uuid.uuid4()).replace('-',''), huxing, size, img_src_url])
        
        # 部分户型图有分页, 如: http://data.house.sina.com.cn/sc127009/huxing/#wt_source=data6_tpdh_hxt       
        next_url = response.xpath(u"//div[@class='sPageBox']//a[contains(text(),'下一页')]/@href").extract_first()
        if next_url:
            self.logger.debug(u'进入楼盘户型图下一页:' + next_url )
            yield scrapy.Request(url = next_url,meta={'house_item':item},callback=self.parse_item_huxing)
        else:
            self.logger.info(u'此楼盘链接处理完毕: ' + item['index_url'])
            yield item
    
    
