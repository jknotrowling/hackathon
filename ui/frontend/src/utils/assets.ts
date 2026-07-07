const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export function resolveImageUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) {
    return url;
  }

  if (url.startsWith('/')) {
    return `${API_URL}${url}`;
  }

  return `${API_URL}/${url}`;
}
