export type ISODateString = string; 
export interface AnalysisInput {
  query: string;
  webResources: Array<{
    title: string;
    description: string;
    url?: string;
  }>;
  financialData: Array<{
    symbol: string;
    company: string;
    sector: string;
    currentPrice: number;
    priceChange: { percentage: string };
    marketCap: string;
    peRatio: number;
    analystRating: string;
    recentNews: Array<{
      title: string;
      source: string;
    }>;
  }>;
}

export interface CombinedResponse {  
  query: string;  
  summary: string;  
  webResources: WebSearchResult[];  
  financialData: FinancialData[];  
}

export interface WebSearchResult {
  title: string;
  snippet: string;
  url: string;
}
export interface FinancialData {
  symbol: string;
  stockData: StockData;
  analystRecommendations: AnalystRecommendation;
  companyInfo: CompanyInfo;
  recentNews: CompanyNews[];
  error?: string;
}

export interface SearchResponse {
  results: WebSearchResult[];
  success: boolean;
  error?: string;
}

export interface AnalysisResult {
  summary: string;
  detailedAnalysis: string;
  timestamp: string;
} 

export interface AdvancedAnalysisInput {  
  analysis?: {  
    type?: string;  
    detailedAnalysis?: string;  
  };  
}

export interface WebSearchCompletionData {
  query: string;
  resultCount: number;
  resultSummary?: string;
  results: WebSearchResult[];
}

export interface FinanceDataCompletionData {
  query: string;
  symbols: string[];
  resultCount: number;
  resultSummary: string;
}

export interface ResponseCompletionData {
  query: string;
  timestamp: string;
  response: {
    query: string;
    summary: string;
    webResources: WebSearchCompletionData[];
    financialData: FinanceDataCompletionData[];
  };
}

export interface StockData {
  symbol: string;
  price: number;
  change: number;
  volume: number;
  marketCap: number;
  peRatio: number;
  dividend: number;
}

export interface AnalystRecommendation {
  buy: number;
  hold: number;
  sell: number;
  targetPrice: number;
}

export interface CompanyInfo {
  name: string;
  sector: string;
  employees: number;
  founded: number;
  headquarters: string;
}

export interface CompanyNews {
  title: string;
  date: ISODateString;
  source: string;
  url: string;
}

// Zod schemas for runtime validation
import { z } from 'zod';

export const ISODateStringSchema = z.string().datetime();

export const WebSearchResultSchema = z.object({
  title: z.string(),
  snippet: z.string(),
  url: z.string().url()
});

export const StockDataSchema = z.object({
  symbol: z.string(),
  price: z.number(),
  change: z.number(),
  volume: z.number(),
  marketCap: z.number(),
  peRatio: z.number(),
  dividend: z.number()
});

export const AnalystRecommendationSchema = z.object({
  buy: z.number(),
  hold: z.number(),
  sell: z.number(),
  targetPrice: z.number()
});

export const CompanyInfoSchema = z.object({
  name: z.string(),
  sector: z.string(),
  employees: z.number(),
  founded: z.number(),
  headquarters: z.string()
});

export const CompanyNewsSchema = z.object({
  title: z.string(),
  date: ISODateStringSchema,
  source: z.string(),
  url: z.string().url()
});

export const FinancialDataSchema = z.object({
  symbol: z.string(),
  stockData: StockDataSchema,
  analystRecommendations: AnalystRecommendationSchema,
  companyInfo: CompanyInfoSchema,
  recentNews: z.array(CompanyNewsSchema),
  error: z.string().optional()
});

export const CombinedResponseSchema = z.object({
  query: z.string(),
  summary: z.string(),
  webResources: z.array(WebSearchResultSchema),
  financialData: z.array(FinancialDataSchema)
});

export const SearchResponseSchema = z.object({
  results: z.array(WebSearchResultSchema),
  success: z.boolean(),
  error: z.string().optional()
});

export const AnalysisResultSchema = z.object({
  summary: z.string(),
  detailedAnalysis: z.string(),
  timestamp: z.string()
});

export const AnalysisInputSchema = z.object({
  query: z.string(),
  webResources: z.array(z.object({
    title: z.string(),
    description: z.string(),
    url: z.string().url().optional()
  })),
  financialData: z.array(z.object({
    symbol: z.string(),
    company: z.string(),
    sector: z.string(),
    currentPrice: z.number(),
    priceChange: z.object({
      percentage: z.string()
    }),
    marketCap: z.string(),
    peRatio: z.number(),
    analystRating: z.string(),
    recentNews: z.array(z.object({
      title: z.string(),
      source: z.string()
    }))
  }))
});
