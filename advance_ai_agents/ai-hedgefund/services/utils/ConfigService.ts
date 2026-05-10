import fs from 'fs/promises';
import path from 'path';

export interface CompanyMapping {
  companyName: string;
  tickerSymbol: string;
  lastUpdated: string;
}

export interface ConfigData {
  companyMappings: CompanyMapping[];
  knownTickers: string[];
  commonWords: string[];
  lastUpdated: string;
  version: string;
}

export class ConfigService {
  private configPath: string;
  private configData: ConfigData | null = null;
  private lastLoadTime: number = 0;
  private readonly CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

  constructor(configPath?: string) {
    this.configPath = configPath || path.join(process.cwd(), 'config', 'company-mappings.json');
  }

  public async getCompanyMappings(): Promise<[string, string][]> {
    const config = await this.loadConfig();
    return config.companyMappings.map(mapping => [mapping.companyName, mapping.tickerSymbol]);
  }

  public async getKnownTickers(): Promise<string[]> {
    const config = await this.loadConfig();
    return config.knownTickers;
  }

  public async getCommonWords(): Promise<string[]> {
    const config = await this.loadConfig();
    return config.commonWords;
  }

  public async getLastUpdated(): Promise<string> {
    const config = await this.loadConfig();
    return config.lastUpdated;
  }

  public async isConfigStale(): Promise<boolean> {  
    const config = await this.loadConfig();  
    const lastUpdated = new Date(config.lastUpdated).getTime();  
    if (isNaN(lastUpdated)) {  
      console.warn('Invalid lastUpdated date in config, treating as stale');  
      return true;  
    }  
    const now = Date.now();  
    return (now - lastUpdated) > this.CACHE_DURATION;  
  } 

  public async updateCompanyMappings(mappings: CompanyMapping[]): Promise<void> {
    const config = await this.loadConfig();
    config.companyMappings = mappings;
    config.lastUpdated = new Date().toISOString();
    await this.saveConfig(config);
  }

  public async addCompanyMapping(companyName: string, tickerSymbol: string): Promise<void> {
    const config = await this.loadConfig();
    const existingIndex = config.companyMappings.findIndex(
      mapping => mapping.companyName === companyName
    );

    const newMapping: CompanyMapping = {
      companyName,
      tickerSymbol,
      lastUpdated: new Date().toISOString()
    };

    if (existingIndex >= 0) {
      config.companyMappings[existingIndex] = newMapping;
    } else {
      config.companyMappings.push(newMapping);
    }

    config.lastUpdated = new Date().toISOString();
    await this.saveConfig(config);
  }

  private async loadConfig(): Promise<ConfigData> {  
    const now = Date.now();  
    
    // Return cached config if it's still fresh  
    if (this.configData && (now - this.lastLoadTime) < this.CACHE_DURATION) {  
      return this.configData;  
    }  

    // Ensure config directory exists  
    const configDir = path.dirname(this.configPath);  
    try {  
      await fs.mkdir(configDir, { recursive: true });  
    } catch (error) {  
      console.error('Error creating config directory:', error);  
      return this.createDefaultConfig();  
    }  

    // Try to load existing config  
    try {  
      const configContent = await fs.readFile(this.configPath, 'utf-8');  
      this.configData = JSON.parse(configContent);  
      this.lastLoadTime = now;  
      return this.configData!;  
    } catch (error) {  
      // If file doesn't exist or is invalid, create default config  
      console.log('Creating default company mappings configuration...');  
      this.configData = this.createDefaultConfig();  
      try {  
        await this.saveConfig(this.configData);  
      } catch (saveError) {  
        console.error('Error saving default configuration:', saveError);  
      }  
      this.lastLoadTime = now;  
      return this.configData;  
    }  
  }

  private async saveConfig(config: ConfigData): Promise<void> {
    try {
      const configDir = path.dirname(this.configPath);
      await fs.mkdir(configDir, { recursive: true });
      await fs.writeFile(this.configPath, JSON.stringify(config, null, 2), 'utf-8');
    } catch (error) {
      console.error('Error saving configuration:', error);
      throw error;
    }
  }

  private createDefaultConfig(): ConfigData {
    return {
      companyMappings: [
        { companyName: 'APPLE', tickerSymbol: 'AAPL', lastUpdated: new Date().toISOString() },
        { companyName: 'MICROSOFT', tickerSymbol: 'MSFT', lastUpdated: new Date().toISOString() },
        { companyName: 'GOOGLE', tickerSymbol: 'GOOGL', lastUpdated: new Date().toISOString() },
        { companyName: 'ALPHABET', tickerSymbol: 'GOOGL', lastUpdated: new Date().toISOString() },
        { companyName: 'AMAZON', tickerSymbol: 'AMZN', lastUpdated: new Date().toISOString() },
        { companyName: 'META', tickerSymbol: 'META', lastUpdated: new Date().toISOString() },
        { companyName: 'FACEBOOK', tickerSymbol: 'META', lastUpdated: new Date().toISOString() },
        { companyName: 'TESLA', tickerSymbol: 'TSLA', lastUpdated: new Date().toISOString() },
        { companyName: 'NVIDIA', tickerSymbol: 'NVDA', lastUpdated: new Date().toISOString() },
        { companyName: 'NETFLIX', tickerSymbol: 'NFLX', lastUpdated: new Date().toISOString() },
        { companyName: 'IBM', tickerSymbol: 'IBM', lastUpdated: new Date().toISOString() },
        { companyName: 'INTEL', tickerSymbol: 'INTC', lastUpdated: new Date().toISOString() },
        { companyName: 'AMD', tickerSymbol: 'AMD', lastUpdated: new Date().toISOString() },
        { companyName: 'COCA-COLA', tickerSymbol: 'KO', lastUpdated: new Date().toISOString() },
        { companyName: 'DISNEY', tickerSymbol: 'DIS', lastUpdated: new Date().toISOString() },
        { companyName: 'WALMART', tickerSymbol: 'WMT', lastUpdated: new Date().toISOString() },
        { companyName: 'NIKE', tickerSymbol: 'NKE', lastUpdated: new Date().toISOString() },
        { companyName: 'MCDONALDS', tickerSymbol: 'MCD', lastUpdated: new Date().toISOString() },
        { companyName: 'STARBUCKS', tickerSymbol: 'SBUX', lastUpdated: new Date().toISOString() },
        { companyName: 'COSTCO', tickerSymbol: 'COST', lastUpdated: new Date().toISOString() },
        { companyName: 'VISA', tickerSymbol: 'V', lastUpdated: new Date().toISOString() },
        { companyName: 'MASTERCARD', tickerSymbol: 'MA', lastUpdated: new Date().toISOString() },
        { companyName: 'PAYPAL', tickerSymbol: 'PYPL', lastUpdated: new Date().toISOString() },
        { companyName: 'UBER', tickerSymbol: 'UBER', lastUpdated: new Date().toISOString() },
        { companyName: 'LYFT', tickerSymbol: 'LYFT', lastUpdated: new Date().toISOString() },
        { companyName: 'AIRBNB', tickerSymbol: 'ABNB', lastUpdated: new Date().toISOString() },
        { companyName: 'PINTEREST', tickerSymbol: 'PINS', lastUpdated: new Date().toISOString() },
        { companyName: 'SNAPCHAT', tickerSymbol: 'SNAP', lastUpdated: new Date().toISOString() },
        { companyName: 'TWITTER', tickerSymbol: 'TWTR', lastUpdated: new Date().toISOString() },
        { companyName: 'SPOTIFY', tickerSymbol: 'SPOT', lastUpdated: new Date().toISOString() }
      ],
      knownTickers: [
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'NFLX',
        'IBM', 'INTC', 'AMD', 'KO', 'DIS', 'WMT', 'NKE', 'MCD', 'SBUX', 'COST',
        'V', 'MA', 'PYPL', 'UBER', 'LYFT', 'ABNB', 'PINS', 'SNAP', 'TWTR', 'SPOT',
        'JPM', 'BAC', 'GS', 'MS', 'C', 'WFC', 'BRK.A', 'BRK.B', 'JNJ', 'PG',
        'UNH', 'HD', 'VZ', 'T', 'PFE', 'MRK', 'XOM', 'CVX', 'BA', 'CAT'
      ],
      commonWords: [
        'A', 'I', 'ME', 'MY', 'IT', 'IS', 'BE', 'AM', 'PM', 'THE', 'AND', 'OR', 'IF', 'IN', 'ON', 'AT', 'TO', 'OF', 'BY',
        'FOR', 'AS', 'SO', 'BUT', 'OUT', 'UP', 'FAQ', 'CEO', 'CFO', 'CTO', 'COO', 'SVP', 'VP', 'USA', 'UK', 'EU',
        'WHAT', 'WHO', 'WHY', 'HOW', 'WHEN', 'WHERE', 'WHICH', 'THAT', 'THESE', 'THOSE', 'THEY', 'THIS', 'WILL', 'ABOUT',
        'FROM', 'WITH', 'SHOW', 'GET', 'CAN', 'MAY', 'HAS', 'HAD', 'WAS', 'WERE', 'BEEN', 'NEW', 'OLD', 'BIG', 'TOP', 'DOW',
        'STOCK', 'STOCKS', 'PRICE', 'PRICES', 'MARKET', 'MARKETS', 'TRADE', 'TRADES', 'TRADING', 'BUY', 'SELL',
        'GAIN', 'GAINS', 'LOSS', 'LOSSES', 'PROFIT', 'PROFITS', 'DIVIDEND', 'DIVIDENDS', 'YIELD', 'YIELDS',
        'FUND', 'FUNDS', 'ETF', 'ETFS', 'BOND', 'BONDS', 'VALUE', 'GROWTH', 'INCOME', 'RETURN', 'RETURNS',
        'HIGH', 'LOW', 'OPEN', 'CLOSE', 'VOLUME', 'INFO', 'NEWS', 'DATA', 'REPORT', 'TELL', 'MOST', 'BEST',
        'YES', 'NO', 'NOW', 'THEN', 'HERE', 'THERE', 'YOUR', 'MY', 'HIS', 'HER', 'THEIR', 'OUR'
      ],
      lastUpdated: new Date().toISOString(),
      version: '1.0.0'
    };
  }
}
