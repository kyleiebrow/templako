const CACHE_NAME = 'lako-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/styles.css',
  '/app.js',
  '/static/manifest.json'
];

// Install Service Worker
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
      .then(() => self.skipWaiting())
  );
});

// Activate Service Worker
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Handler - Network first, then cache
self.addEventListener('fetch', event => {
  // Skip API calls to ensure fresh data
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Cache first strategy for static assets
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request).then(response => {
        // Don't cache non-successful responses
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }

        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, responseToCache);
        });

        return response;
      });
    }).catch(() => {
      // Return offline page if available
      return caches.match('/offline.html');
    })
  );
});

// Background Sync for offline posts
self.addEventListener('sync', event => {
  if (event.tag === 'sync-posts') {
    event.waitUntil(syncOfflinePosts());
  }
});

async function syncOfflinePosts() {
  try {
    const db = await openDB();
    const pendingPosts = await db.getAll('pending_posts');
    
    for (const post of pendingPosts) {
      try {
        const response = await fetch('/api/customer/posts', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Session-Token': post.token
          },
          body: JSON.stringify(post.data)
        });
        
        if (response.ok) {
          await db.delete('pending_posts', post.id);
        }
      } catch (error) {
        console.error('Sync failed for post:', error);
      }
    }
  } catch (error) {
    console.error('Sync error:', error);
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('LakoDb', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = event => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('pending_posts')) {
        db.createObjectStore('pending_posts', { keyPath: 'id' });
      }
    };
  });
}
