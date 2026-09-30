export type Role = 'pragmatist' | 'logician' | 'empath';
export type Alignment =
  | 'lawful_good' | 'lawful_neutral' | 'lawful_evil'
  | 'neutral_good' | 'true_neutral' | 'neutral_evil'
  | 'chaotic_good' | 'chaotic_neutral' | 'chaotic_evil';

export interface PersonaStats {
  energy: number;
  openness: number;
  nerve: number;
  attunement: number;
  provocation: number;
  sharpness: number;
  reasoning: number;
}

export interface PersonaConfig {
  role: Role;
  name: string;
  stats: PersonaStats;
  alignment: Alignment;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export class ApiClient {
  constructor(private readonly base = '') {
    if (/^(?:[a-z]+:)?\/\//i.test(base)) {
      throw new TypeError('API base must be relative');
    }
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (/^(?:[a-z]+:)?\/\//i.test(path)) {
      throw new TypeError('API path must be relative');
    }
    const response = await fetch(`${this.base}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers }
    });
    if (!response.ok) {
      const body = await response.text();
      throw new ApiError(response.status, body || response.statusText);
    }
    return response.json() as Promise<T>;
  }

  health(): Promise<{ status: string }> {
    return this.request('/health');
  }
}

export const api = new ApiClient();
