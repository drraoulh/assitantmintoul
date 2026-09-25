import type { MetadataRoute } from 'next';

const SITE = 'https://smartmboa-web.onrender.com';

export default function sitemap(): MetadataRoute.Sitemap {
  const paths = [
    '/',
    '/assistant',
    '/explorer',
    '/destinations',
    '/planifier',
    '/culture',
    '/hotels',
    '/booking',
    '/vision',
    '/mon-voyage',
  ];
  return paths.map((path) => ({
    url: `${SITE}${path}`,
    changeFrequency: path === '/' ? 'daily' : 'weekly',
    priority: path === '/' ? 1 : 0.7,
  }));
}
