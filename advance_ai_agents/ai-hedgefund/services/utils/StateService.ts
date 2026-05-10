export interface IStateOperations {
  get<T>(scope: string, key: string): Promise<T | null>;
  set<T>(scope: string, key: string, value: T): Promise<T>;
  delete(scope: string, key: string): Promise<void | null>;
  clear(scope: string): Promise<void>;
}

export class StateService {
  private state: IStateOperations;
  private defaultScope: string;

  constructor(state: IStateOperations, defaultScope: string) {
    this.state = state;
    if (!defaultScope) {  
      throw new Error("StateService: defaultScope must be a non-empty string");  
    }  
    this.defaultScope = defaultScope; 
  }

  public async get<T>(key: string, scope?: string): Promise<T | null> {
    return this.state.get<T>(scope || this.defaultScope, key);
  }

  public async set<T>(key: string, value: T, scope?: string): Promise<T> {
    return this.state.set<T>(scope || this.defaultScope, key, value);
  }

  public async delete(key: string, scope?: string): Promise<void | null> {
    return this.state.delete(scope || this.defaultScope, key);
  }

  public async clear(scope?: string): Promise<void> {
    return this.state.clear(scope || this.defaultScope);
  }

  public async getMany<T>(keys: string[], scope?: string): Promise<Record<string, T | null>> {
    const results: Record<string, T | null> = {};
    await Promise.allSettled(  
      keys.map(async (key) => {  
        try {  
          results[key] = await this.get<T>(key, scope);  
        } catch (error) {  
          results[key] = null;  
        }  
      })  
    );  
    return results;
  }

  public async setMany(values: Record<string, any>, scope?: string): Promise<void> {  
    await Promise.allSettled(  
      Object.entries(values).map(([key, value]) => this.set(key, value, scope))  
    );  
  }
} 