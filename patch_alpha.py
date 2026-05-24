import re, os

os.chdir(r'c:\CascadeProjects\windsurf-project\CryptoPulse-Signals')

with open('src/alpha_plays/alpha_discovery.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add GemHunter initialization after session/cache lines
old_init = '        self.session = None\n        self.cache: Dict[str, tuple] = {}  # key: (cached_at, result)\n        self.cache_ttl = timedelta(seconds=30)'
new_init = '        self.session = None\n        self.cache: Dict[str, tuple] = {}  # key: (cached_at, result)\n        self.cache_ttl = timedelta(seconds=30)\n        self.gem_hunter = GemHunter()'

if old_init in content:
    content = content.replace(old_init, new_init)
    print('Patched AlphaDiscovery.__init__')
else:
    print('WARNING: Could not find session/cache lines')

# 2. Integrate gem analysis in scan_dexscreener after candidates are built
old_scan = '        # Build and score candidates\n        candidates = []\n        for pair in pairs:\n            candidate = self._parse_dexscreener_pair(pair)\n            if candidate and candidate.overall_score >= self.min_score:\n                candidates.append(candidate)\n        \n        return candidates'

new_scan = '        # Build and score candidates\n        candidates = []\n        for pair in pairs:\n            candidate = self._parse_dexscreener_pair(pair)\n            if candidate and candidate.overall_score >= self.min_score:\n                candidates.append(candidate)\n        \n        # Run Gem Hunter analysis for long-term potential\n        if candidates:\n            try:\n                await self.gem_hunter.ensure_session()\n                for c in candidates:\n                    try:\n                        gem_metrics = await self.gem_hunter.analyze_candidate(c)\n                        self.gem_hunter.enrich_candidate(c, gem_metrics)\n                    except Exception as gem_err:\n                        logger.debug(f"Gem analysis failed for {c.symbol}: {gem_err}")\n            except Exception as e:\n                logger.debug(f"Gem Hunter session failed: {e}")\n        \n        return candidates'

if old_scan in content:
    content = content.replace(old_scan, new_scan)
    print('Patched scan_dexscreener')
else:
    print('WARNING: Could not find scan_dexscreener block')

with open('src/alpha_plays/alpha_discovery.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('alpha_discovery.py patched')
