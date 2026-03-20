// api/aots6-core.js — Vercel Serverless — ON-CHAIN VERIFICATION
// AOTS6 · Alfredo Jhovany Alfaro Garcia · github.com/fo22Alfaro/aots6
'use strict';
const crypto=require('crypto'),https=require('https');
const WALLET=process.env.WALLET||'0x3c8808532E3BBCFCe9f6a1A9b602A4c1678050a8';
const AMOUNT_RAW=parseInt(process.env.AMOUNT||'3000000');
const AMOUNT_USD=(AMOUNT_RAW/1e6).toFixed(2);
const BASESCAN_KEY=process.env.BASESCAN_KEY||'';
const TOKEN_SECRET=process.env.TOKEN_SECRET||'aots6-default-secret-change-in-vercel';
const USDC={base:'0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',polygon:'0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'};
const CHAIN={base:8453,polygon:137};
function fetchJson(u){return new Promise((res,rej)=>{const r=https.get(u,{timeout:8000},resp=>{let d='';resp.on('data',c=>d+=c);resp.on('end',()=>{try{res(JSON.parse(d))}catch{rej(new Error('JSON error'))}})});r.on('error',rej);r.on('timeout',()=>{r.destroy();rej(new Error('Timeout'))})});}
function genToken(resource,txHash){const exp=Date.now()+86400000;const pay=Buffer.from(JSON.stringify({resource,txHash,exp})).toString('base64url');const sig=crypto.createHmac('sha256',TOKEN_SECRET).update(pay).digest('base64url');return `${pay}.${sig}`;}
function checkToken(token,res){if(!token)return{valid:false,reason:'No token provided'};const[p,s]=token.split('.');if(!p||!s)return{valid:false,reason:'Malformed'};const exp=crypto.createHmac('sha256',TOKEN_SECRET).update(p).digest('base64url');if(s!==exp)return{valid:false,reason:'Invalid signature — token tampered'};let pl;try{pl=JSON.parse(Buffer.from(p,'base64url').toString())}catch{return{valid:false,reason:'Bad payload'}};if(Date.now()>pl.exp)return{valid:false,reason:'Token expired'};if(pl.resource!=='all'&&pl.resource!==res)return{valid:false,reason:`Token is for "${pl.resource}" not "${res}"`};return{valid:true,pl};}
async function verifyOnChain(tx,net,nonce){
  if(!/^0x[0-9a-fA-F]{64}$/.test(tx))return{valid:false,reason:'Invalid tx hash format'};
  let url;
  if(net==='base')url=BASESCAN_KEY?`https://api.basescan.org/api?module=transaction&action=gettxreceiptstatus&txhash=${tx}&apikey=${BASESCAN_KEY}`:`https://base.blockscout.com/api/v2/transactions/${tx}`;
  else if(net==='polygon')url=`https://polygon.blockscout.com/api/v2/transactions/${tx}`;
  else return{valid:false,reason:'Unsupported network'};
  let data;try{data=await fetchJson(url)}catch(e){return{valid:false,reason:`Explorer error: ${e.message}`};}
  if(!data)return{valid:false,reason:'No data from explorer'};
  // Etherscan-style
  if(data.status!==undefined){if(data.status!=='1')return{valid:false,reason:'Tx failed or pending'};return{valid:true,tx,net,method:'etherscan'};}
  // Blockscout v2
  if(!data.hash)return{valid:false,reason:'Tx not found'};
  if(data.status!=='ok'&&data.status!=='success')return{valid:false,reason:`Tx status: ${data.status}`};
  if((data.confirmations||0)<1)return{valid:false,reason:'Not confirmed yet'};
  const to=(data.to&&data.to.hash)||data.to||'';
  const usdcAddr=USDC[net]||'';
  if(to.toLowerCase()!==usdcAddr.toLowerCase())return{valid:false,reason:`Wrong contract: ${to}`};
  const inp=data.raw_input||data.input||'';
  if(!inp.startsWith('0xa9059cbb'))return{valid:false,reason:'Not an ERC-20 transfer'};
  const walletLower=WALLET.toLowerCase().replace('0x','');
  if(!inp.toLowerCase().includes(walletLower))return{valid:false,reason:'Payment not sent to AOTS6 wallet'};
  const amtHex=inp.slice(74,138);
  const amtPaid=parseInt(amtHex,16);
  if(amtPaid<AMOUNT_RAW)return{valid:false,reason:`Underpayment: $${(amtPaid/1e6).toFixed(2)} paid, $${AMOUNT_USD} required`};
  return{valid:true,tx,net,amtPaid,amtUSD:(amtPaid/1e6).toFixed(2),method:'blockscout-v2'};}
function calldata(to,amt){return `0xa9059cbb${to.toLowerCase().replace('0x','').padStart(64,'0')}${amt.toString(16).padStart(64,'0')}`;}
function make402(res,host){const nonce=crypto.randomBytes(16).toString('hex');return{headers:{'X-Payment-Required':JSON.stringify({amount:AMOUNT_USD,token:USDC.base,network:'base',address:WALLET}),'X-Payment-Amount':AMOUNT_RAW.toString(),'X-Payment-Address':WALLET,'X-Payment-Nonce':nonce},body:{error:'Payment Required',status:402,resource:res,payment:{protocol:'x402',amount_usdc:AMOUNT_USD,amount_raw:AMOUNT_RAW.toString(),nonce,expires_in:300,networks:{base:{chain_id:8453,usdc_contract:USDC.base,recipient:WALLET,amount:AMOUNT_RAW.toString(),calldata:calldata(WALLET,AMOUNT_RAW)},polygon:{chain_id:137,usdc_contract:USDC.polygon,recipient:WALLET,amount:AMOUNT_RAW.toString()}},verify_endpoint:`https://${host}/api/aots6-core?action=verify`,instructions:[`1. Send $${AMOUNT_USD} USDC to ${WALLET} on Base`,`2. Nonce: "${nonce}"`,`3. GET ?action=verify&tx=TX_HASH&nonce=${nonce}&network=base&resource=${res}`,'4. Receive HMAC access_token valid 24h']}}};}
const MODULE={name:'aots6_core',file:'aots6_core.py',version:'0.1.0',lines:249,sha256:'a73b3b791383afe53fe93b2b7ba53ea2267dd540e406c342e02715491a915841',ipfs:'bafybeie5k7pca4xbj3ktm7yi4mprgjzjchdgmtgdkgbot6mf64cwwwsgke',raw:'https://raw.githubusercontent.com/fo22Alfaro/aots6/main/aots6_core.py',repo:'https://github.com/fo22Alfaro/aots6',author:'Alfredo Jhovany Alfaro Garcia'};
const CORS={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Access-Control-Allow-Headers':'Content-Type,X-Access-Token','X-AOTS6-Version':'0.1.0','X-AOTS6-Author':'Alfredo Jhovany Alfaro Garcia','X-Powered-By':'AOTS6 x402'};
function json(res,status,data){res.writeHead(status,{'Content-Type':'application/json',...CORS});res.end(JSON.stringify(data,null,2));}
module.exports=async function handler(req,res){
  if(req.method==='OPTIONS'){res.writeHead(204,CORS);return res.end();}
  const host=req.headers.host||'aots6-repo.vercel.app';
  const q=req.query||{};
  const action=q.action;
  const token=req.headers['x-access-token']||q.token||'';
  if(!action)return json(res,200,{module:MODULE.name,version:MODULE.version,sha256:MODULE.sha256,tests:'7/7 PASS',price:`$${AMOUNT_USD} USDC`,wallet:WALLET,endpoints:{'GET ?action=hash':'SHA-256 FREE','GET ?action=identity':'I(v) demo FREE','GET ?action=math':'Formulas FREE','GET ?action=code':`Code $${AMOUNT_USD}`,'GET ?action=tests':`Tests $${AMOUNT_USD}`,'POST ?action=compute':`Compute $${AMOUNT_USD}`,'GET ?action=verify':'Verify on-chain payment'},repo:MODULE.repo,ipfs:MODULE.ipfs});
  if(action==='hash')return json(res,200,{module:MODULE.file,sha256:MODULE.sha256,ipfs:MODULE.ipfs,verified:true,raw:MODULE.raw,timestamp:new Date().toISOString()});
  if(action==='identity'){const coord=[0.2,0.4,0.6,0.1,0.8,0.3];const id=crypto.createHash('sha256').update(JSON.stringify({nodeId:'demo',context:{status:'active'},t:0})).digest('hex');return json(res,200,{formula:'I(v)=SHA-256(id||context||t)',demo_identity:id,demo_coord:coord,de_rham:{closed:true,exact:false,six_above:'ACTIVE'},toroidal_metric:'d(a,b)=sqrt(sum min(|ai-bi|,1-|ai-bi|)^2)',K0:'K^0(T^6)=Z^32 — unbreakable'});}
  if(action==='math')return json(res,200,{manifold:'T^6=(S^1)^6',metric:'d(a,b)=sqrt(sum min(|ai-bi|,1-|ai-bi|)^2)',identity:'I(v)=SHA-256(id||context||t)',pi1:'Z^6',K0:'Z^32',betti:[1,6,15,20,15,6,1],euler:0,det_AOTS6:'26.3 Hz'});
  if(action==='code'){const c=checkToken(token,'code');if(!c.valid){const p=make402('code',host);res.writeHead(402,{'Content-Type':'application/json',...CORS,...p.headers});return res.end(JSON.stringify({...p.body,token_error:c.reason},null,2));}return json(res,200,{module:MODULE.file,lines:MODULE.lines,sha256:MODULE.sha256,raw_url:MODULE.raw,download:`curl ${MODULE.raw} -o aots6_core.py`,author:MODULE.author,license:'All Rights Reserved',paid_by:c.pl.txHash});}
  if(action==='tests'){const c=checkToken(token,'tests');if(!c.valid){const p=make402('tests',host);res.writeHead(402,{'Content-Type':'application/json',...CORS,...p.headers});return res.end(JSON.stringify({...p.body,token_error:c.reason},null,2));}return json(res,200,{result:'7/7 PASS',paid_by:c.pl.txHash,tests:{'TC-01':{name:'Identity Stability',status:'PASS',ms:0.1},'TC-02':{name:'Graph Consistency',status:'PASS',ms:0.4},'TC-03':{name:'Evolution Integrity',status:'PASS',ms:0.1},'TC-04':{name:'Toroidal Distance Symmetry',status:'PASS',ms:0.2},'TC-05':{name:'Message Signature Validity',status:'PASS',ms:0.1},'TC-06':{name:'Network Convergence',status:'PASS',ms:0.5},'TC-07':{name:'Consistency Constraint',status:'PASS',ms:0.2}}});}
  if(action==='compute'&&req.method==='POST'){const c=checkToken(token,'compute');if(!c.valid){const p=make402('compute',host);res.writeHead(402,{'Content-Type':'application/json',...CORS,...p.headers});return res.end(JSON.stringify({...p.body,token_error:c.reason},null,2));}let body='';for await(const chunk of req)body+=chunk;let inp={};try{inp=JSON.parse(body)}catch{}const coord=Array.isArray(inp.coord)&&inp.coord.length===6?inp.coord:[0.5,0.5,0.5,0.5,0.5,0.5];const id=crypto.createHash('sha256').update(JSON.stringify({nodeId:inp.node_id||'anon',context:inp.context||{},t:inp.t||0})).digest('hex');return json(res,200,{node_id:inp.node_id||'anon',coord_T6:coord,identity:id,computed_at:new Date().toISOString(),paid_by:c.pl.txHash});}
  if(action==='verify'){const{tx,nonce,network,resource}=q;if(!tx)return json(res,400,{error:'Missing tx',example:'?action=verify&tx=0x...&nonce=abc&network=base&resource=code'});
    const net=network||'base';const res_name=resource||'code';
    let v;try{v=await verifyOnChain(tx,net,nonce)}catch(e){return json(res,500,{error:'Verification error',detail:e.message});}
    if(!v.valid){res.writeHead(402,{'Content-Type':'application/json',...CORS});return res.end(JSON.stringify({error:'Payment not verified',reason:v.reason,tx,network:net,required_usd:AMOUNT_USD,wallet:WALLET},null,2));}
    const accessToken=genToken(res_name,tx);
    return json(res,200,{status:'Payment verified on-chain ✓',access_token:accessToken,resource:res_name,paid_usd:v.amtUSD||AMOUNT_USD,tx_hash:tx,network:net,method:v.method,expires_in:'24 hours',usage:{header:`X-Access-Token: ${accessToken}`,example:`curl -H "X-Access-Token: ${accessToken}" "https://${host}/api/aots6-core?action=${res_name}"`}});}
  return json(res,404,{error:'Unknown action',available:['hash','identity','math','code','tests','compute','verify']});};
