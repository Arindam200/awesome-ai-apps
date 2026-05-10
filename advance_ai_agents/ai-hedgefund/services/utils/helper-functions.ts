import { AdvancedAnalysisInput } from "./types";

interface AnalysisData {  
  summary?: string;  
  detailedAnalysis?: string;  
  [key: string]: any; // For additional properties  
}  

interface AnalysisInputs {  
  generalAnalysis?: AnalysisData;  
  portfolioAnalysis?: AnalysisData;  
  riskAnalysis?: AnalysisData;  
  technicalAnalysis?: AnalysisData;  
  fundamentalAnalysis?: AnalysisData;  
}

interface AnalysisConfig {  
  key: string;  
  title: string;  
  propertyName: keyof AnalysisInputs;  
}  

const ANALYSIS_CONFIGS: AnalysisConfig[] = [  
  { key: 'general', title: 'General Market Analysis', propertyName: 'generalAnalysis' },  
  { key: 'portfolio', title: 'Portfolio Management Insights', propertyName: 'portfolioAnalysis' },  
  { key: 'risk', title: 'Risk Assessment & Management', propertyName: 'riskAnalysis' },  
  { key: 'technical', title: 'Technical Analysis', propertyName: 'technicalAnalysis' },  
  { key: 'fundamental', title: 'Fundamental Analysis', propertyName: 'fundamentalAnalysis' }  
];
// Helper function to determine the current analysis type from the input
export function getCurrentAnalysisType(input: AdvancedAnalysisInput): string {
  // Check for specific analysis types in the input
  if (input.analysis && input.analysis.type === 'portfolio') return 'portfolio.analysis.completed';
  if (input.analysis && input.analysis.type === 'risk') return 'risk.analysis.completed';
  if (input.analysis && input.analysis.type === 'technical') return 'technical.analysis.completed';
  if (input.analysis && input.analysis.type === 'fundamental') return 'fundamental.analysis.completed';
  
  // Check for analysis content to determine type
  if (input.analysis && input.analysis.detailedAnalysis) {
    const analysisText = input.analysis.detailedAnalysis.toLowerCase();
    if (analysisText.includes('portfolio') || analysisText.includes('asset allocation')) return 'portfolio.analysis.completed';
    if (analysisText.includes('risk') || analysisText.includes('volatility')) return 'risk.analysis.completed';
    if (analysisText.includes('technical') || analysisText.includes('chart pattern')) return 'technical.analysis.completed';
    if (analysisText.includes('fundamental') || analysisText.includes('valuation')) return 'fundamental.analysis.completed';
  }
  
  // Default to general analysis
  return 'analysis.completed';
}

// Helper function to get the state key for storing analysis results
export function getAnalysisStateKey(analysisType: string): string | null {
  switch (analysisType) {
    case 'analysis.completed': return 'ai.analysis';
    case 'portfolio.analysis.completed': return 'portfolio.analysis';
    case 'risk.analysis.completed': return 'risk.analysis';
    case 'technical.analysis.completed': return 'technical.analysis';
    case 'fundamental.analysis.completed': return 'fundamental.analysis';
    default: return null;
  }
}

// Helper function to create comprehensive report
export function createComprehensiveReport(analyses: AnalysisInputs): {
  summary: string;
  timestamp: string;
  sections: Record<string, any>;
  metadata: {
    totalAnalyses: number;
    completedAnalyses: number;
    analysisTypes: string[];
  };
  executiveSummary?: string;
} {
  const report: {
    summary: string;
    timestamp: string;
    sections: Record<string, any>;
    metadata: {
      totalAnalyses: number;
      completedAnalyses: number;
      analysisTypes: string[];
    };
    executiveSummary?: string;
  } = {
    summary: 'Comprehensive Financial Analysis Report',
    timestamp: new Date().toISOString(),
    sections: {} as Record<string, any>,
    metadata: {
      totalAnalyses: ANALYSIS_CONFIGS.length,
      completedAnalyses: 0,
      analysisTypes: [] as string[]
    }
  };
  
  let completedCount = 0;
  
  // Use configuration to build sections dynamically
  ANALYSIS_CONFIGS.forEach(config => {
    const analysis = analyses[config.propertyName];
    if (analysis) {
      report.sections[config.key] = {
        title: config.title,
        summary: analysis.summary || `${config.key} analysis completed`,
        details: analysis.detailedAnalysis || analysis,
        type: config.key
      };
      completedCount++;
      report.metadata.analysisTypes.push(config.key);
    }
  });
  
  report.metadata.completedAnalyses = completedCount;
  
  // Add executive summary using the exported function
  report.executiveSummary = generateExecutiveSummary(
    Object.values(report.sections).map((section: any) => section.summary)
  );
  
  return report;
}



// Helper function to format the combined response
export function formatCombinedResponse(query: string | null, webSearchResults: any[], financeData: any[]): any {
  const response: any = {
    query: query || 'Unknown query',
    summary: `Results for "${query || 'Unknown query'}"`,
    webResources: [],
    financialData: []
  };
  
  // Format web search results
  if (webSearchResults && webSearchResults.length > 0) {
    response.webResources = webSearchResults.map(result => ({
      title: result.title,
      description: result.snippet,
      url: result.url
    }));
  }
  
  // Format financial data
  if (financeData && financeData.length > 0) {
    response.financialData = financeData.map(data => {
      const { symbol, stockData, analystRecommendations, companyInfo, recentNews } = data;
      
      return {
        symbol,
        company: companyInfo.name,
        sector: companyInfo.sector,
        currentPrice: formatCurrency(stockData.price),
        priceChange: {  
          value: formatCurrency(stockData.change),  
          percentage: stockData.price !== 0 
            ? `${(stockData.change / stockData.price * 100).toFixed(2)}%`  
            : 'N/A'  
        },
        marketCap: formatLargeNumber(stockData.marketCap),
        peRatio: stockData.pe.toFixed(2),
        analystRating: formatAnalystRating(analystRecommendations),
        recentNews: recentNews.map((news: any) => ({
          title: news.title,
          date: news.date,
          source: news.source
        }))
      };
    });
  }
  
  return response;
}

// Internal formatting helper functions
function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

// Export the formatting functions that are used in query-api.step.ts
export function formatLargeNumber(value: number): string {
  if (value >= 1e12) {
    return `$${(value / 1e12).toFixed(2)}T`;
  } else if (value >= 1e9) {
    return `$${(value / 1e9).toFixed(2)}B`;
  } else if (value >= 1e6) {
    return `$${(value / 1e6).toFixed(2)}M`;
  } else {
    return `$${value.toFixed(2)}`;
  }
}

export function formatAnalystRating(recommendations: any): string {
  const { buy, hold, sell } = recommendations;
  const total = buy + hold + sell;
  
  if (total === 0) return 'No ratings';
  
  const buyPercentage = (buy / total * 100).toFixed(0);
  
  if (buy > hold && buy > sell) {
    return `Buy (${buyPercentage}% of analysts recommend)`;
  } else if (hold > buy && hold > sell) {
    return `Hold (${(hold / total * 100).toFixed(0)}% of analysts recommend)`;
  } else {
    return `Sell (${(sell / total * 100).toFixed(0)}% of analysts recommend)`;
  }
}

export function generateExecutiveSummary(summaries: string[]): string {
  const validSummaries = summaries.filter(Boolean);
  
  if (validSummaries.length === 0) {
    return 'Comprehensive financial analysis completed with multiple specialized perspectives.';
  }
  
  return `Comprehensive analysis completed with ${validSummaries.length} specialized perspectives: ${validSummaries.join('; ')}`;
} 