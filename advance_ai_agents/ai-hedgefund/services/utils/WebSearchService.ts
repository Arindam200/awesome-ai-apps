import axios from 'axios';
import * as dotenv from 'dotenv';

dotenv.config();
import { SearchResponse, WebSearchResult } from './types';

export class WebSearchService {
  private searchUrl: string;
  private apiKey: string;

  constructor(apiKey: string = process.env.SERPER_API_KEY || '', searchUrl: string = 'https://google.serper.dev/search') {
    this.searchUrl = searchUrl;
    this.apiKey = apiKey;
  }

  public async search(query: string): Promise<SearchResponse> {
    try {
      if (!this.apiKey) {
        throw new Error('No API key provided for search service');
      }

      const response = await axios.post(this.searchUrl, {
        q: query,
        gl: 'us',
        hl: 'en',
        num: 10
      }, {
        headers: {
          'X-API-KEY': this.apiKey,
          'Content-Type': 'application/json'
        }
      });

      if (response.data && response.data.organic && Array.isArray(response.data.organic)) {
        const results = this.parseSerperResults(response.data);
        return {
          results: results,
          success: true
        };
      } else {
        console.warn('API response format not recognized');
        return {
          results: [],
          success: false,
          error: 'Invalid API response format'
        };
      }
    } catch (error) {
      console.error('Web search error:', error);
      return {
        results: [],
        success: false,
        error: error instanceof Error ? error.message : 'Unknown search error'
      };
    }
  }

  private parseSerperResults(data: any): WebSearchResult[] {
    const results: WebSearchResult[] = [];
    
    if (data.organic && Array.isArray(data.organic)) {
      data.organic.forEach((result: any) => {
        results.push({
          title: result.title || 'Untitled',
          snippet: result.snippet || 'No description available',
          url: result.link || '#'
        });
      });
    }
    
    if (data.peopleAlsoAsk && Array.isArray(data.peopleAlsoAsk)) {
      data.peopleAlsoAsk.forEach((item: any) => {
        results.push({
          title: item.question || 'Question',
          snippet: item.snippet || item.answer || 'No answer available',
          url: item.link || '#'
        });
      });
    }
      
    if (data.knowledgeGraph) {
      const kg = data.knowledgeGraph;
      if (kg.title && (kg.description || kg.snippet)) {
        const getKnowledgeGraphUrl = (kg: any) => {  
          return kg.siteLinks?.[0]?.link || kg.website || '#';  
        };
        results.push({
          title: kg.title,
          snippet: kg.description || kg.snippet || 'Knowledge graph result',
          url: getKnowledgeGraphUrl(kg)
        });
      }
    }
    
    return results;
  }
} 