import axios from 'axios';
import yahooFinance from 'yahoo-finance2';
import { FinancialData, StockData, AnalystRecommendation, CompanyInfo, CompanyNews } from '../types';
import { ConfigService } from '../utils/ConfigService';


const ALPHA_VINTAGE_KEY = process.env.ALPHA_VINTAGE_KEY;  
if (!ALPHA_VINTAGE_KEY) {  
  throw new Error('ALPHA_VINTAGE_KEY environment variable is required');  
}

const ALPHA_VANTAGE_BASE_URL = 'https://www.alphavantage.co/query';
const API_TIMEOUT = 15000;

const axiosInstance = axios.create({  
  timeout: API_TIMEOUT  
});

const yahooModuleOptions = { 
  validateResult: false as const,
  timeout: 10000,
  retry: 2,
  headers: {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
  }
};

interface AlphaVantageQuote {
  'Global Quote'?: {
    '01. symbol': string;
    '05. price': string;
    '06. volume': string;
    '09. change': string;
    [key: string]: string;
  };
}

interface AlphaVantageCompanyOverview {
  Name?: string;
  Sector?: string;
  FullTimeEmployees?: string;
  IPOYear?: string;
  Address?: string;
  [key: string]: string | undefined;
}

interface AlphaVantageNewsItem {
  title: string;
  time_published: string;
  source: string;
  url: string;
  [key: string]: any;
}

interface AlphaVantageNewsFeed {
  feed?: AlphaVantageNewsItem[];
  [key: string]: any;
}

interface YahooFinanceQuote {
  regularMarketPrice?: number;
  regularMarketChange?: number;
  regularMarketVolume?: number;
  marketCap?: number;
  trailingPE?: number;
  dividendYield?: number;
  [key: string]: any;
}

interface YahooFinanceQuoteSummary {
  summaryDetail?: {
    marketCap?: number;
    trailingPE?: number;
    dividendYield?: number;
  };
  recommendationTrend?: {
    trend?: Array<{
      strongBuy?: number;
      buy?: number;
      hold?: number;
      sell?: number;
      strongSell?: number;
    }>;
  };
  financialData?: {
    targetMeanPrice?: number;
  };
  assetProfile?: {
    longName?: string;
    sector?: string;
    fullTimeEmployees?: number;
    foundedYear?: number;
    city?: string;
    country?: string;
  };
  [key: string]: any;
}

interface YahooFinanceNewsItem {
  title: string;
  providerPublishTime: number;
  publisher: string;
  link: string;
}

interface YahooFinanceNewsResponse {
  news?: YahooFinanceNewsItem[];
  [key: string]: any;
}

export class FinanceDataService {
  private configService: ConfigService;
  private companyMappingsCache: Map<string, string> | null = null;
  private knownTickersCache: Set<string> | null = null;
  private commonWordsCache: Set<string> | null = null;
  private lastCacheUpdate: number = 0;
  private readonly CACHE_DURATION = 60 * 60 * 1000; // 1 hour in milliseconds

  constructor(configService?: ConfigService) {
    this.configService = configService || new ConfigService();
  }

  public async extractPotentialSymbols(query: string): Promise<string[]> {
    const symbolRegex = /\b[A-Z0-9]{1,5}(?:\.[A-Z]{1,2})?(?::[A-Z]{2,4})?\b/g; 
    
    // Load mappings from external configuration
    const [knownCompanies, knownTickers, commonWords] = await Promise.all([
      this.loadCompanyMappings(),
      this.loadKnownTickers(),
      this.loadCommonWords()
    ]);
    
    const upperQuery = query.toUpperCase();
    const companyMatches = Array.from(knownCompanies.entries())
      .filter(([company]) => upperQuery.includes(company))
      .map(([_, symbol]) => symbol);
    
    if (companyMatches.length > 0) {
      return companyMatches;
    }
    
    const matches = query.toUpperCase().match(symbolRegex) || [];
    
    const knownMatches = matches.filter(symbol => knownTickers.has(symbol));
    
    if (knownMatches.length > 0) {
      return knownMatches;
    }
    
    const filteredSymbols = matches
      .filter(match => !commonWords.has(match))
      .filter(symbol => symbol.length >= 2);
    
    return Array.from(new Set(filteredSymbols));
  }

  // Load from external source  
  private async loadCompanyMappings(): Promise<Map<string, string>> {  
    // Check if cache is still valid
    if (this.companyMappingsCache && (Date.now() - this.lastCacheUpdate) < this.CACHE_DURATION) {
      return this.companyMappingsCache;
    }

    try {
      // Load from config service
      const mappings = await this.configService.getCompanyMappings();
      this.companyMappingsCache = new Map(mappings);
      this.lastCacheUpdate = Date.now();
      return this.companyMappingsCache;
    } catch (error) {
      console.error('Error loading company mappings:', error);
      // Return empty map as fallback
      return new Map();
    }
  }

  private async loadKnownTickers(): Promise<Set<string>> {
    // Check if cache is still valid
    if (this.knownTickersCache && (Date.now() - this.lastCacheUpdate) < this.CACHE_DURATION) {
      return this.knownTickersCache;
    }

    try {
      const tickers = await this.configService.getKnownTickers();
      this.knownTickersCache = new Set(tickers);
      this.lastCacheUpdate = Date.now();
      return this.knownTickersCache;
    } catch (error) {
      console.error('Error loading known tickers:', error);
      // Return empty set as fallback
      return new Set();
    }
  }

  private async loadCommonWords(): Promise<Set<string>> {
    // Check if cache is still valid
    if (this.commonWordsCache && (Date.now() - this.lastCacheUpdate) < this.CACHE_DURATION) {
      return this.commonWordsCache;
    }

    try {
      const words = await this.configService.getCommonWords();
      this.commonWordsCache = new Set(words);
      this.lastCacheUpdate = Date.now();
      return this.commonWordsCache;
    } catch (error) {
      console.error('Error loading common words:', error);
      // Return empty set as fallback
      return new Set();
    }
  }

  public async refreshMappings(): Promise<void> {
    try {
      // Clear cache to force reload
      this.companyMappingsCache = null;
      this.knownTickersCache = null;
      this.commonWordsCache = null;
      this.lastCacheUpdate = 0;
      
      // Preload mappings
      await Promise.all([
        this.loadCompanyMappings(),
        this.loadKnownTickers(),
        this.loadCommonWords()
      ]);
      
      console.log('Company mappings refreshed successfully');
    } catch (error) {
      console.error('Error refreshing mappings:', error);
    }
  }

  public async addCompanyMapping(companyName: string, tickerSymbol: string): Promise<void> {
    try {
      await this.configService.addCompanyMapping(companyName, tickerSymbol);
      // Clear cache to force reload
      this.companyMappingsCache = null;
      this.lastCacheUpdate = 0;
      console.log(`Added mapping: ${companyName} -> ${tickerSymbol}`);
    } catch (error) {
      console.error('Error adding company mapping:', error);
      throw error;
    }
  }

  public async isConfigStale(): Promise<boolean> {
    return await this.configService.isConfigStale();
  }


  public async getFinancialData(symbol: string): Promise<FinancialData> {
    try {
      return {
        symbol,
        stockData: await this.getStockData(symbol),
        analystRecommendations: await this.getAnalystRecommendations(symbol),
        companyInfo: await this.getCompanyInfo(symbol),
        recentNews: await this.getCompanyNews(symbol)
      };
    } catch (error) {
      console.error(`Error retrieving financial data for ${symbol}:`, error);
      return {
        symbol,
        stockData: {
          symbol,
          price: 0,
          change: 0,
          volume: 0,
          marketCap: 0,
          peRatio: 0,
          dividend: 0
        },
        analystRecommendations: {
          buy: 0,
          hold: 0,
          sell: 0,
          targetPrice: 0
        },
        companyInfo: {
          name: `${symbol} Corporation`,
          sector: 'Unknown',
          employees: 0,
          founded: 0,
          headquarters: 'Unknown'
        },
        recentNews: [],
        error: `Failed to retrieve financial data for ${symbol}`
      };
    }
  }

  private async getStockData(symbol: string): Promise<StockData> {
    try {
      const alphaVantageData = await this.getAlphaVantageStockData(symbol);
      if (alphaVantageData) {
        return alphaVantageData;
      }
      
      const yahooData = await this.getYahooFinanceStockData(symbol);
      if (yahooData) {
        return yahooData;
      }
      
      console.warn(`All data sources failed for symbol: ${symbol}`);
      return {
        symbol,
        price: 0,
        change: 0,
        volume: 0,
        marketCap: 0,
        peRatio: 0,
        dividend: 0
      };
    } catch (error) {
      console.error(`Error fetching stock data for ${symbol}:`, error);
      return {
        symbol,
        price: 0,
        change: 0,
        volume: 0,
        marketCap: 0,
        peRatio: 0,
        dividend: 0
      };
    }
  }


  private async getAlphaVantageStockData(symbol: string): Promise<StockData | null> {
    try {
      const response = await axiosInstance.get<AlphaVantageQuote>(ALPHA_VANTAGE_BASE_URL, {
        params: {
          function: 'GLOBAL_QUOTE',
          symbol,
          apikey: ALPHA_VINTAGE_KEY
        }
      });

      const quote = response.data['Global Quote'];
      
      if (quote && quote['01. symbol']) {
        const price = parseFloat(quote['05. price']);  
        const change = parseFloat(quote['09. change']);  
        const volume = parseInt(quote['06. volume'], 10);  
        if (isNaN(price) || isNaN(change) || isNaN(volume)) {  
          console.warn(`Invalid numeric data received for ${symbol}`);  
          return null;  
        }  
        
        try {
          const yahooData = await this.getYahooFinanceSummaryData(symbol);
          
          return {
            symbol,
            price,
            change,
            volume,
            marketCap: yahooData?.marketCap || 0,
            peRatio: yahooData?.pe || 0,
            dividend: yahooData?.dividend || 0
          };
        } catch (error) {
          console.error(`Error fetching Yahoo summary data for ${symbol}:`, error);
          return {
            symbol,
            price,
            change,
            volume,
            marketCap: 0,
            peRatio: 0,
            dividend: 0
          };
        }
      } 
      
      return null;
    } catch (error) {
      console.error(`Error fetching Alpha Vantage data for ${symbol}:`, error);
      return null;
    }
  }


  private async getYahooFinanceStockData(symbol: string): Promise<StockData | null> {
    try {
      const yahooQuote: YahooFinanceQuote = await yahooFinance.quote(symbol, {}, yahooModuleOptions);
      
      if (yahooQuote && yahooQuote.regularMarketPrice !== undefined) {
        return {
          symbol,
          price: yahooQuote.regularMarketPrice || 0,
          change: yahooQuote.regularMarketChange || 0,
          volume: yahooQuote.regularMarketVolume || 0,
          marketCap: yahooQuote.marketCap || 0,
          peRatio: yahooQuote.trailingPE || 0,
          dividend: yahooQuote.dividendYield || 0
        };
      }
      
      console.warn(`Invalid or unknown stock symbol: ${symbol}`);
      return null;
    } catch (error) {
      console.error(`Error fetching Yahoo quote for ${symbol}:`, error);
      
      if (error instanceof Error) {
        const errorMessage = error.message.toLowerCase();
        if (errorMessage.includes('crumb') || errorMessage.includes('guce.yahoo.com')) {
          console.warn(`Yahoo Finance authentication issue for ${symbol}, trying alternative approach`);
          return null;
        }
      }
      
      return null;
    }
  }

  private async getYahooFinanceSummaryData(symbol: string): Promise<{ marketCap: number; pe: number; dividend: number } | null> {
    try {
      const quoteSummary: YahooFinanceQuoteSummary = await yahooFinance.quoteSummary(symbol, {
        modules: ['summaryDetail'],
        ...yahooModuleOptions
      });
      
      const summaryDetail = quoteSummary?.summaryDetail || {};
      
      return {
        marketCap: summaryDetail.marketCap || 0,
        pe: summaryDetail.trailingPE || 0,
        dividend: summaryDetail.dividendYield ? summaryDetail.dividendYield * 100 : 0
      };
    } catch (error) {
      console.error(`Error fetching Yahoo summary data for ${symbol}:`, error);
      return null;
    }
  }

  private async getAnalystRecommendations(symbol: string): Promise<AnalystRecommendation> {
    try {
      const quoteSummary: YahooFinanceQuoteSummary = await yahooFinance.quoteSummary(symbol, {
        modules: ['recommendationTrend', 'financialData'],
        ...yahooModuleOptions
      });
      
      let buyCount = 0;
      let holdCount = 0;
      let sellCount = 0;
      let targetPrice = 0;
      
      if (quoteSummary?.recommendationTrend?.trend?.[0]) {
        const trend = quoteSummary.recommendationTrend.trend[0];
        buyCount = (trend.strongBuy || 0) + (trend.buy || 0);
        holdCount = trend.hold || 0;
        sellCount = (trend.sell || 0) + (trend.strongSell || 0);
      }
      
      if (quoteSummary?.financialData?.targetMeanPrice) {
        targetPrice = quoteSummary.financialData.targetMeanPrice;
      }
      
      return {
        buy: buyCount,
        hold: holdCount,
        sell: sellCount,
        targetPrice
      };
      
    } catch (error) {
      console.error(`Error fetching analyst recommendations for ${symbol}:`, error);
      return {
        buy: 0,
        hold: 0,
        sell: 0,
        targetPrice: 0
      };
    }
  }

  private async getCompanyInfo(symbol: string): Promise<CompanyInfo> {
    try {
      const alphaVantageInfo = await this.getAlphaVantageCompanyInfo(symbol);
      if (alphaVantageInfo) {
        return alphaVantageInfo;
      }
      
      const yahooInfo = await this.getYahooFinanceCompanyInfo(symbol);
      if (yahooInfo) {
        return yahooInfo;
      }
      
      return {
        name: `${symbol} Corporation`,
        sector: 'Unknown',
        employees: 0,
        founded: 0,
        headquarters: 'Unknown'
      };
    } catch (error) {
      console.error(`Error fetching company info for ${symbol}:`, error);
      return {
        name: `${symbol} Corporation`,
        sector: 'Unknown',
        employees: 0,
        founded: 0,
        headquarters: 'Unknown'
      };
    }
  }

  private async getAlphaVantageCompanyInfo(symbol: string): Promise<CompanyInfo | null> {
    try {
      const response = await axiosInstance.get<AlphaVantageCompanyOverview>(ALPHA_VANTAGE_BASE_URL, {
        params: {
          function: 'OVERVIEW',
          symbol,
          apikey: ALPHA_VINTAGE_KEY
        }
      });
      
      if (response.data && response.data.Name) {
        return {
          name: response.data.Name,
          sector: response.data.Sector || 'Unknown',
          employees: parseInt(response.data.FullTimeEmployees || '0', 10),
          founded: parseInt(response.data.IPOYear || '0', 10),
          headquarters: response.data.Address || 'Unknown'
        };
      }
      
      return null;
    } catch (error) {
      console.error(`Error fetching Alpha Vantage company info for ${symbol}:`, error);
      return null;
    }
  }

  private async getYahooFinanceCompanyInfo(symbol: string): Promise<CompanyInfo | null> {
    try {
      const assetProfile: YahooFinanceQuoteSummary = await yahooFinance.quoteSummary(symbol, {
        modules: ['assetProfile'],
        ...yahooModuleOptions
      });
      
      if (assetProfile?.assetProfile) {
        const profile = assetProfile.assetProfile;
        
        return {
          name: profile.longName || `${symbol} Corporation`,
          sector: profile.sector || 'Unknown',
          employees: profile.fullTimeEmployees || 0,
          founded: profile.foundedYear || new Date().getFullYear(),
          headquarters: profile.city && profile.country ? 
            `${profile.city}, ${profile.country}` : 'Unknown'
        };
      }
      
      return null;
    } catch (error) {
      console.error(`Error fetching Yahoo profile for ${symbol}:`, error);
      return null;
    }
  }


  private async getCompanyNews(symbol: string): Promise<CompanyNews[]> {
    try {
      const alphaVantageNews = await this.getAlphaVantageNews(symbol);
      if (alphaVantageNews && alphaVantageNews.length > 0) {
        return alphaVantageNews;
      }
      
      const yahooNews = await this.getYahooFinanceNews(symbol);
      if (yahooNews && yahooNews.length > 0) {
        return yahooNews;
      }
      
      return [
        {
          title: `${symbol} Recent News`,
          date: new Date().toISOString(),
          source: 'Financial Times',
          url: `https://finance.yahoo.com/quote/${symbol}/news`
        }
      ];
    } catch (error) {
      console.error(`Error fetching company news for ${symbol}:`, error);
      return [
        {
          title: `${symbol} Recent News`,
          date: new Date().toISOString(),
          source: 'Financial Times',
          url: `https://finance.yahoo.com/quote/${symbol}/news`
        }
      ];
    }
  }

  private async getAlphaVantageNews(symbol: string): Promise<CompanyNews[] | null> {
    try {
      const response = await axiosInstance.get<AlphaVantageNewsFeed>(ALPHA_VANTAGE_BASE_URL, {
        params: {
          function: 'NEWS_SENTIMENT',
          tickers: symbol,
          limit: 5,
          apikey: ALPHA_VINTAGE_KEY
        }
      });
      
      if (response.data && response.data.feed && response.data.feed.length > 0) {
        return response.data.feed.map((item: AlphaVantageNewsItem) => ({
          title: item.title,
          date: item.time_published,
          source: item.source,
          url: item.url
        }));
      }
      
      return null;
    } catch (error) {
      console.error(`Error fetching Alpha Vantage news for ${symbol}:`, error);
      return null;
    }
  }

  private async getYahooFinanceNews(symbol: string): Promise<CompanyNews[] | null> {
    try {
      const newsData: YahooFinanceNewsResponse = await yahooFinance.search(symbol, { newsCount: 5 }, yahooModuleOptions);
      
      if (newsData && newsData.news && newsData.news.length > 0) {
        return newsData.news.map((item: YahooFinanceNewsItem) => ({
          title: item.title,
          date: new Date(item.providerPublishTime * 1000).toISOString(),
          source: item.publisher,
          url: item.link
        }));
      }
      
      return null;
    } catch (error) {
      console.error(`Error fetching Yahoo news for ${symbol}:`, error);
      return null;
    }
  }
}