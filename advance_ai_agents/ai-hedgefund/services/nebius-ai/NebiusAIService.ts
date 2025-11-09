import { AnalysisInput, AnalysisResult } from '../types';

export class NebiusAIService {  
  private baseURL: string;  
  private model: string;  
  private getApiKey: () => string;  

  /**  
   * Creates a new NebiusAIService instance  
   * @param apiKey Nebius API key, defaults to environment variable  
   * @param baseURL Nebius base URL, defaults to environment variable  
   * @param model Model to use, defaults to environment variable  
   */  
  constructor(apiKey?: string, baseURL?: string, model?: string) {
    const resolvedApiKey = apiKey || (typeof process !== 'undefined' ? process.env.NEBIUS_API_KEY : '') || '';
    this.baseURL = baseURL || (typeof process !== 'undefined' ? process.env.NEBIUS_BASE_URL : '') || 'https://api.tokenfactory.nebius.com/v1';
    this.model = model || (typeof process !== 'undefined' ? process.env.NEBIUS_MODEL : '') || 'Qwen/Qwen3-235B-A22B';  
    
    if (!resolvedApiKey) {  
      throw new Error('Nebius API key not found');  
    }  
    
    this.getApiKey = () => resolvedApiKey;  
  }

  /**
   * Performs fundamental analysis using Nebius AI API
   * @param data Analysis input data
   * @returns Analysis result
   */

  private async callNebiusAnalysisAPI(
    prompt: string,
    systemContent: string,
    errorContext: string,
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<AnalysisResult> {
    try {
      const requestPayload = {
        model: this.model,
        messages: [
          {
            role: 'system',
            content: systemContent
          },
          {
            role: 'user',
            content: [
              {
                type: 'text',
                text: prompt
              }
            ]
          }
        ],
        max_tokens: options.maxTokens || 1000,
        temperature: options.temperature || 0.7
      };

      const response = await fetch(`${this.baseURL}chat/completions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.getApiKey()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestPayload)
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Nebius API error: ${response.status} - ${errorText}`);
      }

      const result = await response.json();  
      
      if (!result || typeof result !== 'object') {  
        throw new Error('Invalid response format from Nebius API');  
      }  
      
      if (!result.choices || !Array.isArray(result.choices) || result.choices.length === 0) {  
        throw new Error('No choices in Nebius API response');  
      }  
      
      const analysisText: string = result.choices?.[0]?.message?.content || `No ${errorContext} generated`;  
      
      if (!analysisText || typeof analysisText !== 'string') {  
        throw new Error('Invalid analysis content in response');  
      }  

      return {  
        summary: this.extractSummary(analysisText),  
        detailedAnalysis: analysisText,  
        timestamp: new Date().toISOString()  
      }; 
      
    } catch (error) {
      console.error(`Error calling Nebius AI API for ${errorContext}:`, error);
      throw new Error(`Nebius AI API error: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Performs fundamental analysis using Nebius AI API
   * @param data Analysis input data
   * @param options Configuration options for the analysis
   * @returns Analysis result
   */
  public async performFundamentalAnalysis(
    data: AnalysisInput, 
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<AnalysisResult> {
    const prompt = this.buildFundamentalAnalysisPrompt(data);
    const systemContent =
      'You are a professional fundamental analyst specializing in company valuation, financial ratios, and long-term investment analysis. Focus on intrinsic value, competitive advantages, and business fundamentals.';
    return this.callNebiusAnalysisAPI(prompt, systemContent, 'fundamental analysis', options);
  }

  /**
   * Performs portfolio analysis using Nebius AI API
   * @param data Analysis input data
   * @param options Configuration options for the analysis
   * @returns Analysis result
   */
  public async performPortfolioAnalysis(
    data: AnalysisInput, 
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<AnalysisResult> {
    const prompt = this.buildPortfolioAnalysisPrompt(data);
    const systemContent =
      'You are a professional portfolio manager specializing in asset allocation, diversification strategies, and portfolio optimization. Focus on risk-adjusted returns and strategic positioning.';
    return this.callNebiusAnalysisAPI(prompt, systemContent, 'portfolio analysis', options);
  }

  /**
   * Performs risk analysis using Nebius AI API
   * @param data Analysis input data
   * @param options Configuration options for the analysis
   * @returns Analysis result
   */
  public async performRiskAnalysis(
    data: AnalysisInput, 
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<AnalysisResult> {
    const prompt = this.buildRiskAnalysisPrompt(data);
    const systemContent =
      'You are a professional risk manager specializing in market risk, credit risk, and operational risk assessment. Focus on risk identification, measurement, and mitigation strategies.';
    return this.callNebiusAnalysisAPI(prompt, systemContent, 'risk analysis', options);
  }

  /**
   * Performs technical analysis using Nebius AI API
   * @param data Analysis input data
   * @param options Configuration options for the analysis
   * @returns Analysis result
   */
  public async performTechnicalAnalysis(
    data: AnalysisInput, 
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<AnalysisResult> {
    const prompt = this.buildTechnicalAnalysisPrompt(data);
    const systemContent =
      'You are a professional technical analyst specializing in chart patterns, technical indicators, and market timing. Focus on price action, support/resistance levels, and trend analysis.';
    return this.callNebiusAnalysisAPI(prompt, systemContent, 'technical analysis', options);
  }

  /**
   * Performs financial analysis using Nebius AI API
   * @param data Analysis input data
   * @param options Configuration options for the analysis
   * @returns Analysis result
   */
  public async performAnalysis(
    data: AnalysisInput, 
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<AnalysisResult> {
    const prompt = this.buildAnalysisPrompt(data);
    const systemContent =
      'You are a professional financial analyst. Analyze the financial data provided and give insights, recommendations, and a market outlook. Format your response in markdown with sections.';
    return this.callNebiusAnalysisAPI(prompt, systemContent, 'analysis', options);
  }

  /**
   * Helper to format web research section for prompts.
   */
  private formatWebResearch(webResources: Array<{ title: string; description: string }>): string {
    if (!webResources || webResources.length === 0) return '';
    let section = "Web Research:\n";
    webResources.forEach((resource, idx) => {
      section += `${idx + 1}. ${resource.title}\n   ${resource.description}\n`;
    });
    section += "\n";
    return section;
  }

  /**
   * Helper to format financial data section for prompts.
   */
  private formatFinancialData(financialData: Array<{
    symbol: string;
    company: string;
    sector: string;
    currentPrice: number | string;
    priceChange: { percentage: string };
    marketCap: string;
    peRatio: number | string;
    analystRating: string;
    recentNews?: Array<{ title: string; source: string }>;
  }>): string {
    if (!financialData || financialData.length === 0) return '';
    let section = "Financial Data:\n";
    financialData.forEach((item) => {
      if (!item) return;
      
      // Safe property access with fallbacks
      const symbol = item.symbol || 'N/A';
      const company = item.company || 'N/A';
      const sector = item.sector || 'N/A';
      const currentPrice = item.currentPrice || 'N/A';
      const priceChangePercentage = item.priceChange?.percentage || 'N/A';
      const marketCap = item.marketCap || 'N/A';
      const peRatio = item.peRatio || 'N/A';
      const analystRating = item.analystRating || 'N/A';
      
      section += `Stock: ${symbol} (${company})\n`;
      section += `Sector: ${sector}\n`;
      section += `Price: ${currentPrice} (${priceChangePercentage})\n`;
      section += `Market Cap: ${marketCap}\n`;
      section += `P/E Ratio: ${peRatio}\n`;
      section += `Analyst Rating: ${analystRating}\n`;
      
      if (item.recentNews && Array.isArray(item.recentNews) && item.recentNews.length > 0) {
        section += "Recent News:\n";
        item.recentNews.forEach((news) => {
          if (!news) return;
          const title = news.title || 'N/A';
          const source = news.source || 'N/A';
          section += `  - ${title} (${source})\n`;
        });
      }
      section += "\n";
    });
    return section;
  }

  /**
   * Builds a prompt for fundamental analysis
   * @param data Input data for analysis
   * @returns Formatted prompt string
   */
  private buildFundamentalAnalysisPrompt(data: AnalysisInput): string {
    const { query, webResources, financialData } = data;
    let prompt = `You are a senior equity research analyst. Perform a thorough fundamental analysis${query ? ` for: "${query}"` : ''}.\n\n`;
    prompt += this.formatWebResearch(webResources);
    prompt += this.formatFinancialData(financialData);

    prompt += `
Please provide a detailed fundamental analysis covering:
- Company valuation and intrinsic value (include DCF or comparable analysis if possible)
- Financial health and stability (liquidity, solvency, profitability ratios)
- Competitive position, market share, and economic moat
- Growth prospects, business model, and management quality
- Long-term investment thesis and expected return drivers
- Key risks, uncertainties, and red flags

Structure your response in markdown with clear sections, bullet points, and tables where appropriate. Use concise, actionable language.`;

    return prompt;
  }

  /**
   * Builds a prompt for portfolio analysis
   * @param data Input data for analysis
   * @returns Formatted prompt string
   */
  private buildPortfolioAnalysisPrompt(data: AnalysisInput): string {
    const { query, webResources, financialData } = data;
    let prompt = `You are a professional portfolio manager. Conduct a comprehensive portfolio analysis${query ? ` for: "${query}"` : ''}.\n\n`;
    prompt += this.formatWebResearch(webResources);
    prompt += this.formatFinancialData(financialData);

    prompt += `
Please provide a portfolio analysis including:
- Asset allocation recommendations (with rationale)
- Diversification and correlation assessment
- Risk-adjusted return optimization (e.g., Sharpe ratio, drawdown)
- Sector and geographic allocation insights
- Portfolio rebalancing suggestions and timing
- Alternative investment or hedging considerations

Present your analysis in markdown with clear sections, summary tables, and actionable recommendations.`;

    return prompt;
  }

  /**
   * Builds a prompt for risk analysis
   * @param data Input data for analysis
   * @returns Formatted prompt string
   */
  private buildRiskAnalysisPrompt(data: AnalysisInput): string {
    const { query, webResources, financialData } = data;
    let prompt = `You are a risk management expert. Perform a detailed risk analysis${query ? ` for: "${query}"` : ''}.\n\n`;
    prompt += this.formatWebResearch(webResources);
    prompt += this.formatFinancialData(financialData);

    prompt += `
Please provide a risk analysis covering:
- Market risk (volatility, beta, macro factors)
- Company-specific and sector risks
- Correlation and concentration risks
- Downside risk and stress scenarios
- Risk mitigation and hedging strategies
- Regulatory or geopolitical risks

Format your response in markdown with clear sections, risk tables, and practical recommendations.`;

    return prompt;
  }

  /**
   * Builds a prompt for technical analysis
   * @param data Input data for analysis
   * @returns Formatted prompt string
   */
  private buildTechnicalAnalysisPrompt(data: AnalysisInput): string {
    const { query, webResources, financialData } = data;
    let prompt = `You are a technical analysis specialist. Conduct a technical analysis${query ? ` for: "${query}"` : ''}.\n\n`;
    prompt += this.formatWebResearch(webResources);
    prompt += this.formatFinancialData(financialData);

    prompt += `
Please provide a technical analysis including:
- Price action and trend direction (with timeframes)
- Key support and resistance levels
- Technical indicators (RSI, MACD, moving averages, etc.)
- Chart pattern recognition (e.g., head and shoulders, triangles)
- Volume and momentum analysis
- Entry/exit point recommendations and stop-loss levels

Present your analysis in markdown with annotated sections and, if possible, ASCII charts or tables.`;

    return prompt;
  }

  /**
   * Builds a prompt for general financial analysis
   * @param data Input data for analysis
   * @returns Formatted prompt string
   */
  private buildAnalysisPrompt(data: AnalysisInput): string {
    const { query, webResources, financialData } = data;
    let prompt = `You are a financial analyst. Analyze the following financial information${query ? ` for: "${query}"` : ''}.\n\n`;
    prompt += this.formatWebResearch(webResources);
    prompt += this.formatFinancialData(financialData);

    prompt += `
Based on this information, provide:
- A comprehensive market and company analysis
- Investment recommendations (buy/sell/hold, with rationale)
- Risk assessment and mitigation
- Future outlook and catalysts
- Alternative investment ideas

Format your response in markdown with clear sections, bullet points, and summary tables.`;

    return prompt;
  }

  /**
   * Extracts a concise summary from a detailed analysis
   * @param analysis Full analysis text
   * @returns Brief summary
   */
  private extractSummary(analysis: string): string {

    if (!analysis || !analysis.trim()) {  
      return 'No analysis summary available';  
    }
    
    const firstParagraph = analysis.split('\n\n')[0].trim();
    if (firstParagraph.length <= 150) {
      return firstParagraph;
    }
    
    // Find the last space before 147 characters
    const truncateAt = firstParagraph.lastIndexOf(' ', 147);
    if (truncateAt > 0) {
      return firstParagraph.substring(0, truncateAt) + '...';
    }
    
    // Fallback if no space found
    return firstParagraph.substring(0, 147) + '...';
  }
}