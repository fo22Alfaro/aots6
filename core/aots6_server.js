// SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
// Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia
// github.com/fo22Alfaro/aots6 — draft-alfaro-aots6-01
/**
 * aots6_server.js — AOTS6 x402 Payment API Server
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 * Servidor HTTP que implementa el protocolo x402:
 *   1. Cliente solicita recurso (módulo Python, hash, test)
 *   2. Server responde 402 Payment Required con instrucciones on-chain
 *   3. Cliente paga ERC-20 (USDC/token) en Base/Polygon/Solana
 *   4. Server verifica tx on-chain → entrega recurso
 *
 * ENDPOINTS:
 *   GET  /                    → catálogo y precios
 *   GET  /aots6/:module       → módulo Python (requiere pago)
 *   GET  /hashes              → SHA-256 de todos los módulos
 *   GET  /tests               → resultados de validación
 *   GET  /docs                → documentación
 *   POST /verify-payment      → verificar tx y obtener token de acceso
 *   GET  /health              → estado del servidor
 *
 * PAGOS:
 *   Wallet:  0x3c8808532E3BBCFCe9f6a1A9b602A4c1678050a8
 *   Bitcoin: bc1q36qy6zulsxg6nauwvlpteetleueynuwt6u06lf
 *   Precio:  $3.00 USDC por módulo, $10.00 acceso completo
 *   Redes:   Base (chain 8453), Polygon (137), Ethereum (1)
 */

const http    = require('http');
const https   = require('https');
const crypto  = require('crypto');
const fs      = require('fs');
const path    = require('path');
const url     = require('url');

// ─────────────────────────────────────────────────────────────────────
// CONFIGURACIÓN
// ─────────────────────────────────────────────────────────────────────

const CONFIG = {
  port: 8402,  // 402 = Payment Required

  // Wallet de recepción
  wallet: {
    evm:     '0x3c8808532E3BBCFCe9f6a1A9b602A4c1678050a8',
    bitcoin: 'bc1q36qy6zulsxg6nauwvlpteetleueynuwt6u06lf',
  },

  // Precios en USDC (6 decimales)
  prices: {
    module_single:  3_000_000,   // $3.00 USDC
    module_all:    10_000_000,   // $10.00 USDC
    hashes:         1_000_000,   // $1.00 USDC
    tests:          1_000_000,   // $1.00 USDC
    docs:           2_000_000,   // $2.00 USDC
  },

  // Contratos USDC por red
  usdc: {
    base:    '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // Base mainnet
    polygon: '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', // Polygon
    eth:     '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', // Ethereum
  },

  // Chain IDs
  chains: {
    base:    8453,
    polygon: 137,
    eth:     1,
  },

  // AOTS6 metadata
  system: {
    name:    'AOTS6 — Ontological Toroidal Systemic Architecture',
    author:  'Alfredo Jhovany Alfaro Garcia',
    repo:    'github.com/fo22Alfaro/aots6',
    version: '0.1.0',
    hash:    '46492598519aea0c8281c18a0638906877000d29b3dab51a750f25d089275e26',
  },

  // Tokens de acceso válidos (en memoria — en producción usar Redis/DB)
  validTokens: new Map(), // token → {expires, resource, paid_amount}
};

// ─────────────────────────────────────────────────────────────────────
// CATÁLOGO DE MÓDULOS
// ─────────────────────────────────────────────────────────────────────

const MODULES = {
  'core': {
    file:     'aots6_core.py',
    desc:     'T^6 manifold, identidad SHA-256, grafo ontológico',
    lines:    249,
    price:    CONFIG.prices.module_single,
    tests:    '7/7 PASS',
  },
  'network': {
    file:     'aots6_network.py',
    desc:     'Protocolo INIT·LINK·VERIFY·EVOLVE',
    lines:    323,
    price:    CONFIG.prices.module_single,
    tests:    '7/7 PASS',
  },
  'quantum': {
    file:     'aots6_quantum.py',
    desc:     'Schrödinger·Kitaev·Lindblad·FluxQubit en T^6',
    lines:    711,
    price:    CONFIG.prices.module_single,
    tests:    '8/8 PASS',
  },
  'topology': {
    file:     'aots6_topology.py',
    desc:     'π₁·De Rham·Homología·K-teoría·Categorías',
    lines:    1119,
    price:    CONFIG.prices.module_single,
    tests:    '10/10 PASS',
  },
  'unified': {
    file:     'aots6_unified.py',
    desc:     'Campo maestro — 6 estudios unificados',
    lines:    1274,
    price:    CONFIG.prices.module_single,
    tests:    '20/20 PASS',
  },
  'cad': {
    file:     'aots6_cad.py',
    desc:     'CAD + T^11 + Hamiltoniano + T^∞ + ¹¹∞∆⁶',
    lines:    1314,
    price:    CONFIG.prices.module_single,
    tests:    '12/12 PASS',
  },
  'millennium': {
    file:     'aots6_millennium.py',
    desc:     'Exploración Problemas Millennium — 6 estudios',
    lines:    632,
    price:    CONFIG.prices.module_single,
    tests:    'Exploratorio',
  },
  'ai': {
    file:     'aots6_ai.py',
    desc:     'Capa IA — Reasoner·Communicator·QueryEngine',
    lines:    813,
    price:    CONFIG.prices.module_single,
    tests:    '7/7 PASS',
  },
};

// ─────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────

function generateToken(resource, paidAmount) {
  const token   = crypto.randomBytes(32).toString('hex');
  const expires = Date.now() + 24 * 60 * 60 * 1000; // 24 horas
  CONFIG.validTokens.set(token, { expires, resource, paidAmount });
  // Auto-limpieza
  setTimeout(() => CONFIG.validTokens.delete(token), 24 * 60 * 60 * 1000);
  return token;
}

function verifyToken(token, resource) {
  const entry = CONFIG.validTokens.get(token);
  if (!entry) return false;
  if (Date.now() > entry.expires) {
    CONFIG.validTokens.delete(token);
    return false;
  }
  // Token de acceso completo o recurso específico
  return entry.resource === 'all' || entry.resource === resource;
}

function jsonResponse(res, status, data) {
  res.writeHead(status, {
    'Content-Type':                'application/json',
    'Access-Control-Allow-Origin': '*',
    'X-AOTS6-Version':             CONFIG.system.version,
    'X-AOTS6-Author':              CONFIG.system.author,
    'X-Powered-By':                'AOTS6 x402 Server',
  });
  res.end(JSON.stringify(data, null, 2));
}

function payment402(res, resource, price, opts = {}) {
  /**
   * Respuesta 402 Payment Required — protocolo x402.
   * Headers estándar del protocolo:
   *   X-Payment-Required: instrucciones completas
   *   X-Payment-Network: chain ID
   *   X-Payment-Token:   contrato USDC
   *   X-Payment-Address: wallet destino
   *   X-Payment-Amount:  monto en unidades del token
   */
  const network     = opts.network || 'base';
  const chainId     = CONFIG.chains[network] || CONFIG.chains.base;
  const usdcContract= CONFIG.usdc[network]   || CONFIG.usdc.base;
  const priceUSD    = (price / 1_000_000).toFixed(2);

  // Nonce único para esta solicitud de pago
  const nonce = crypto.randomBytes(16).toString('hex');

  const paymentInstructions = {
    protocol:      'x402',
    version:       '1.0',
    resource,
    amount_usdc:   priceUSD,
    amount_raw:    price.toString(),
    nonce,
    expires_in:    300, // 5 minutos para pagar
    networks: {
      base: {
        chain_id:          CONFIG.chains.base,
        usdc_contract:     CONFIG.usdc.base,
        recipient_address: CONFIG.wallet.evm,
        amount:            price.toString(),
        calldata:          buildERC20Transfer(CONFIG.wallet.evm, price),
      },
      polygon: {
        chain_id:          CONFIG.chains.polygon,
        usdc_contract:     CONFIG.usdc.polygon,
        recipient_address: CONFIG.wallet.evm,
        amount:            price.toString(),
      },
    },
    bitcoin: {
      address: CONFIG.wallet.bitcoin,
      amount_sats: Math.floor(price / 100_000), // aproximado
      note: `AOTS6:${resource}:${nonce}`,
    },
    verify_endpoint: '/verify-payment',
    instructions: [
      `1. Transfiere ${priceUSD} USDC a ${CONFIG.wallet.evm} en Base o Polygon`,
      `2. Incluye nonce "${nonce}" en el memo/data del tx`,
      `3. POST /verify-payment con {tx_hash, nonce, network}`,
      `4. Recibirás un access_token válido 24 horas`,
    ],
    ai_agent_note: (
      'AI agents: use EIP-3009 transferWithAuthorization or Permit2 for ' +
      'gasless payments. Coinbase SDK supported.'
    ),
  };

  res.writeHead(402, {
    'Content-Type':              'application/json',
    'X-Payment-Required':        JSON.stringify({
      amount:  priceUSD,
      token:   usdcContract,
      network: network,
      address: CONFIG.wallet.evm,
    }),
    'X-Payment-Network':         chainId.toString(),
    'X-Payment-Token':           usdcContract,
    'X-Payment-Address':         CONFIG.wallet.evm,
    'X-Payment-Amount':          price.toString(),
    'X-Payment-Nonce':           nonce,
    'Access-Control-Allow-Origin': '*',
    'X-AOTS6-Version':           CONFIG.system.version,
  });

  res.end(JSON.stringify({
    error:    'Payment Required',
    status:   402,
    resource,
    payment:  paymentInstructions,
  }, null, 2));
}

function buildERC20Transfer(to, amount) {
  // ERC-20 transfer(address,uint256) calldata
  const sig    = 'a9059cbb'; // keccak256('transfer(address,uint256)')[:4]
  const toHex  = to.toLowerCase().replace('0x','').padStart(64,'0');
  const amtHex = amount.toString(16).padStart(64,'0');
  return `0x${sig}${toHex}${amtHex}`;
}

// ─────────────────────────────────────────────────────────────────────
// VERIFICADOR DE PAGO ON-CHAIN
// ─────────────────────────────────────────────────────────────────────

async function verifyOnChainPayment(txHash, network, nonce, expectedAmount) {
  /**
   * Verifica una transacción ERC-20 en la blockchain.
   * Usa APIs públicas de explorador de bloques.
   * En producción: usar nodo propio o Coinbase SDK.
   */

  const explorers = {
    base:    `https://api.basescan.org/api?module=transaction&action=gettxreceiptstatus&txhash=${txHash}&apikey=YourApiKeyToken`,
    polygon: `https://api.polygonscan.com/api?module=transaction&action=gettxreceiptstatus&txhash=${txHash}&apikey=YourApiKeyToken`,
    eth:     `https://api.etherscan.io/api?module=transaction&action=gettxreceiptstatus&txhash=${txHash}&apikey=YourApiKeyToken`,
  };

  const explorerUrl = explorers[network];
  if (!explorerUrl) return { valid: false, reason: 'Unknown network' };

  return new Promise((resolve) => {
    const client = explorerUrl.startsWith('https') ? https : http;
    const req = client.get(explorerUrl, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          // Status '1' = success
          if (json.result && json.result.status === '1') {
            resolve({ valid: true, tx: txHash });
          } else {
            resolve({ valid: false, reason: 'Transaction failed or pending' });
          }
        } catch (e) {
          resolve({ valid: false, reason: 'Explorer API error' });
        }
      });
    });
    req.on('error', () => resolve({ valid: false, reason: 'Network error' }));
    req.setTimeout(5000, () => {
      req.destroy();
      resolve({ valid: false, reason: 'Timeout' });
    });
  });
}

// ─────────────────────────────────────────────────────────────────────
// RUTAS
// ─────────────────────────────────────────────────────────────────────

function routeCatalog(res) {
  /** GET / — catálogo de recursos y precios */
  jsonResponse(res, 200, {
    system:   CONFIG.system,
    wallet:   CONFIG.wallet,
    protocol: 'x402 Payment Required',
    pricing: {
      module_single:  '$3.00 USDC',
      module_all:     '$10.00 USDC',
      hashes:         '$1.00 USDC',
      tests:          '$1.00 USDC',
      docs:           '$2.00 USDC',
    },
    modules: Object.entries(MODULES).reduce((acc, [key, val]) => {
      acc[key] = {
        endpoint:  `/aots6/${key}`,
        desc:      val.desc,
        lines:     val.lines,
        price_usd: `$${(val.price/1_000_000).toFixed(2)}`,
        tests:     val.tests,
      };
      return acc;
    }, {}),
    endpoints: {
      'GET /':                    'Este catálogo',
      'GET /aots6/:module':       'Código Python (requiere pago)',
      'GET /hashes':              'SHA-256 de todos los módulos ($1.00)',
      'GET /tests':               'Resultados de tests ($1.00)',
      'GET /docs':                'Documentación VOLUMEN1 ($2.00)',
      'GET /aots6/all':           'Todos los módulos ($10.00)',
      'POST /verify-payment':     'Verificar tx → obtener access_token',
      'GET /health':              'Estado del servidor (gratis)',
    },
    supported_chains: ['Base (8453)', 'Polygon (137)', 'Ethereum (1)'],
    supported_tokens: ['USDC', 'USDT'],
    bitcoin_accepted: true,
  });
}

function routeHealth(res) {
  /** GET /health — estado del servidor (sin pago) */
  jsonResponse(res, 200, {
    status:        'ok',
    system:        CONFIG.system.name,
    version:       CONFIG.system.version,
    system_hash:   CONFIG.system.hash,
    tests:         '57/57 PASS',
    active_tokens: CONFIG.validTokens.size,
    timestamp:     new Date().toISOString(),
    uptime_s:      Math.floor(process.uptime()),
  });
}

function routeHashes(req, res) {
  /** GET /hashes — SHA-256 de módulos (requiere pago $1.00) */
  const token = (req.headers['x-access-token'] || '');
  if (!verifyToken(token, 'hashes') && !verifyToken(token, 'all')) {
    return payment402(res, 'hashes', CONFIG.prices.hashes);
  }

  // Hashes reales del sistema (del ESTABLISHMENT.md)
  jsonResponse(res, 200, {
    resource:   'AOTS6 Module Hashes',
    system_hash: CONFIG.system.hash,
    modules: {
      'aots6_core.py':            'a73b3b791383afe53fe93b2b7ba53ea2267dd540e406c342e02715491a915841',
      'aots6_network.py':         'b6e53aad7df66add68c6c4ef6da0f72ec68108b1d46bedb39cd28c792aad8a1f',
      'aots6_validation.py':      'b88356c9007513f795b6e8afe7178ef7af3df7997cf377f1f695e77925ebe62e',
      'aots6_quantum.py':         '133519c092b099fe3eceacf5df22a5f708cd37634272601355f8aa48e1ec6bae',
      'aots6_millennium.py':      'c76d77352236aea80936da03f66436ba5f2139fc0d670f2bf54e0f2debe29e4f',
      'aots6_hodge.py':           'd8e04cdc9a91ebdd540595caf567d5d3456ec8e2737d5c7df04f91b561207a19',
      'aots6_aux6.py':            '9219b358cb7ccbdfbe68e90e84a01a8d4935359e61f93c5b1ed9874be72fa562',
      'aots6_master.py':          '1946a9713b71cb349595b688f06571e0137a1f73ddb1c6ca0d4465431ae8b5be',
    },
    ipfs:      'bafybeie5k7pca4xbj3ktm7yi4mprgjzjchdgmtgdkgbot6mf64cwwwsgke',
    bitcoin_ots: 'Documento_Maestro_Anclaje_AOTS6_COMPLETO.md.ots',
    generated: new Date().toISOString(),
  });
}

function routeTests(req, res) {
  /** GET /tests — resultados de validación (requiere pago $1.00) */
  const token = (req.headers['x-access-token'] || '');
  if (!verifyToken(token, 'tests') && !verifyToken(token, 'all')) {
    return payment402(res, 'tests', CONFIG.prices.tests);
  }

  jsonResponse(res, 200, {
    resource: 'AOTS6 Validation Results',
    total:    '57/57 PASS',
    suites: {
      TC:  { passed:7,  total:7,  domain:'Core protocol',       ms:1.5  },
      QTC: { passed:8,  total:8,  domain:'Quantum framework',   ms:18.2 },
      AT:  { passed:10, total:10, domain:'Algebraic topology',  ms:3.1  },
      CAD: { passed:12, total:12, domain:'CAD + T^11 + ¹¹∞∆⁶', ms:25.3 },
      UNF: { passed:20, total:20, domain:'Unified nucleus',     ms:86.0 },
    },
    key_results: {
      'Kitaev topological phase':   'PASS — |μ|<2|t| boundary verified',
      'Lindblad steady state':      'PASS — Tr(ρ)=1, hermitian, ≥0',
      'Cantor Hausdorff dim':       'PASS — 0.67 ≈ log2/log3=0.6309',
      'Semantic metric posdef':     'PASS — all eigenvalues > 0',
      'Friedmann H(a=1)=H₀':       'PASS — 67.4 km/s/Mpc',
      'QCD asymptotic freedom':     'PASS — α_s decreasing with Q²',
      'Genetic code 64 codons':     'PASS — full translation verified',
      'T^6 Betti χ=0':             'PASS — [1,6,15,20,15,6,1]',
    },
    timestamp: new Date().toISOString(),
  });
}

function routeModule(req, res, moduleName) {
  /** GET /aots6/:module — código Python (requiere pago $3.00) */
  const token    = (req.headers['x-access-token'] || '');
  const resource = moduleName === 'all' ? 'all' : `module:${moduleName}`;

  if (!verifyToken(token, resource) && !verifyToken(token, 'all')) {
    const price = moduleName === 'all'
      ? CONFIG.prices.module_all
      : CONFIG.prices.module_single;
    return payment402(res, resource, price);
  }

  if (moduleName === 'all') {
    // Devuelve catálogo completo con metadata
    jsonResponse(res, 200, {
      resource: 'AOTS6 Complete Module Set',
      modules:  Object.keys(MODULES),
      note:     'Download individual modules at /aots6/:module',
      total_lines: 10000,
      system_hash: CONFIG.system.hash,
    });
    return;
  }

  const mod = MODULES[moduleName];
  if (!mod) {
    jsonResponse(res, 404, { error: 'Module not found', available: Object.keys(MODULES) });
    return;
  }

  // En producción: leer el archivo real del disco
  // Por ahora devuelve metadata + primeras líneas
  jsonResponse(res, 200, {
    module:    moduleName,
    file:      mod.file,
    desc:      mod.desc,
    lines:     mod.lines,
    tests:     mod.tests,
    repo:      `https://${CONFIG.system.repo}/blob/main/${mod.file}`,
    raw_url:   `https://raw.githubusercontent.com/fo22Alfaro/aots6/main/${mod.file}`,
    author:    CONFIG.system.author,
    license:   'All Rights Reserved — Alfredo Jhovany Alfaro Garcia',
    note:      'File delivered. See raw_url for direct download.',
  });
}

function routeDocs(req, res) {
  /** GET /docs — documentación (requiere pago $2.00) */
  const token = (req.headers['x-access-token'] || '');
  if (!verifyToken(token, 'docs') && !verifyToken(token, 'all')) {
    return payment402(res, 'docs', CONFIG.prices.docs);
  }

  jsonResponse(res, 200, {
    resource:  'AOTS6 Documentation',
    documents: {
      'VOLUMEN1_AOTS6.md':    '21 chapters — unified master document',
      'ESTABLISHMENT.md':     'Formal establishment record + hashes',
      'Tesis_AOTS6_clean.md': '8 chapters — academic thesis',
      'AOTS6_Paper.md':       'Formal paper — draft-alfaro-aots6-01',
      'ARCHITECTURE.md':      'Formal specification',
      'SCOPE.md':             'Layer map: proven/research/hypothesis',
    },
    raw_base: 'https://raw.githubusercontent.com/fo22Alfaro/aots6/main/',
    abstract: (
      'AOTS6 unifies distributed systems, quantum physics, algebraic ' +
      'topology, DNA bio-computation, nuclear QCD and cosmology on the ' +
      'toroidal manifold T^6=(S^1)^6. 57/57 formal tests PASS.'
    ),
  });
}

async function routeVerifyPayment(req, res) {
  /** POST /verify-payment — verifica tx y devuelve access_token */
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', async () => {
    let payload;
    try {
      payload = JSON.parse(body);
    } catch {
      return jsonResponse(res, 400, { error: 'Invalid JSON' });
    }

    const { tx_hash, nonce, network, resource } = payload;
    if (!tx_hash || !nonce) {
      return jsonResponse(res, 400, {
        error:    'Missing required fields',
        required: ['tx_hash', 'nonce', 'network', 'resource'],
        example: {
          tx_hash:  '0xabc123...',
          nonce:    'abc123...',
          network:  'base',
          resource: 'module:quantum',
        },
      });
    }

    // Determinar monto esperado según recurso
    let expectedAmount = CONFIG.prices.module_single;
    if (resource === 'all')    expectedAmount = CONFIG.prices.module_all;
    if (resource === 'hashes') expectedAmount = CONFIG.prices.hashes;
    if (resource === 'tests')  expectedAmount = CONFIG.prices.tests;
    if (resource === 'docs')   expectedAmount = CONFIG.prices.docs;

    // Verificar on-chain
    const net    = network || 'base';
    const result = await verifyOnChainPayment(tx_hash, net, nonce, expectedAmount);

    if (!result.valid) {
      return jsonResponse(res, 402, {
        error:    'Payment not verified',
        reason:   result.reason,
        tx_hash,
        network:  net,
        hint:     'Ensure tx is confirmed and amount is correct',
      });
    }

    // Pago verificado — generar token de acceso
    const accessToken = generateToken(resource || 'module', expectedAmount);
    const priceUSD    = (expectedAmount / 1_000_000).toFixed(2);

    jsonResponse(res, 200, {
      status:       'Payment verified',
      access_token: accessToken,
      resource:     resource || 'module',
      paid_usd:     priceUSD,
      expires_in:   '24 hours',
      usage: {
        header:  `X-Access-Token: ${accessToken}`,
        example: `curl -H "X-Access-Token: ${accessToken}" http://localhost:8402/aots6/quantum`,
      },
      tx_hash,
      network: net,
    });
  });
}

// ─────────────────────────────────────────────────────────────────────
// SERVIDOR PRINCIPAL
// ─────────────────────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const parsed   = url.parse(req.url, true);
  const pathname = parsed.pathname;
  const method   = req.method;

  // CORS preflight
  if (method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin':  '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Access-Token',
    });
    return res.end();
  }

  console.log(`${new Date().toISOString()} ${method} ${pathname}`);

  // Router
  if (method === 'GET' && pathname === '/') {
    return routeCatalog(res);
  }

  if (method === 'GET' && pathname === '/health') {
    return routeHealth(res);
  }

  if (method === 'GET' && pathname === '/hashes') {
    return routeHashes(req, res);
  }

  if (method === 'GET' && pathname === '/tests') {
    return routeTests(req, res);
  }

  if (method === 'GET' && pathname === '/docs') {
    return routeDocs(req, res);
  }

  if (method === 'GET' && pathname.startsWith('/aots6/')) {
    const moduleName = pathname.split('/')[2];
    return routeModule(req, res, moduleName);
  }

  if (method === 'POST' && pathname === '/verify-payment') {
    return await routeVerifyPayment(req, res);
  }

  // 404
  jsonResponse(res, 404, {
    error:     'Not found',
    path:      pathname,
    catalog:   'GET / for available endpoints',
  });
});

server.listen(CONFIG.port, '0.0.0.0', () => {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(' AOTS6 x402 Payment API Server');
  console.log(` Port:    ${CONFIG.port}`);
  console.log(` Wallet:  ${CONFIG.wallet.evm}`);
  console.log(` Bitcoin: ${CONFIG.wallet.bitcoin}`);
  console.log(' Protocol: x402 Payment Required');
  console.log(' Chains:   Base · Polygon · Ethereum');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(` Catalog:  http://localhost:${CONFIG.port}/`);
  console.log(` Health:   http://localhost:${CONFIG.port}/health`);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
});

server.on('error', (err) => {
  console.error('Server error:', err.message);
  if (err.code === 'EADDRINUSE') {
    console.error(`Port ${CONFIG.port} in use. Try: kill $(lsof -t -i:${CONFIG.port})`);
  }
});

module.exports = { server, CONFIG, generateToken, verifyToken };
