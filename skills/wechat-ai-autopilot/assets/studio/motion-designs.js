// Original designs. SMIL is kept in the SVG; preview controls stay outside it.
window.MotionDesigns=(()=>{
  const catalog=[
    {id:'cinema',name:'电影揭幕',use:'科技发布、深度观点、文章开场',description:'光幕拉开、镜头推进与标题显影，深蓝和香槟金。',duration:9,probe:'curtain',auto:true},
    {id:'fold',name:'折页揭晓',use:'金句、提问、结论揭晓',description:'点开朱砂封页，封页上移后露出纸上的结论。',duration:3,probe:'fold',auto:false},
    {id:'carousel',name:'横向轮播',use:'步骤介绍、案例串联、三个要点',description:'三张完整编辑卡片横向接力，停留阅读后继续。',duration:12,probe:'carousel',auto:true},
    {id:'constellation',name:'星轨连线',use:'AI工作流、逻辑关系、机制解释',description:'关系连线逐渐生长，暖金光点绕中心问题流转。',duration:8,probe:'orbit',auto:true},
    {id:'ink',name:'水墨卷轴',use:'文学、人物、文化、思考随笔',description:'画卷从两端展开，山水缓缓移动，文字分层落定。',duration:12,probe:'scroll',auto:true},
    {id:'wipe',name:'双层擦拭',use:'前后对照、误区纠正、认知转变',description:'移动分界线揭示两种提问方式，完整画面相互替换。',duration:10,probe:'wipe',auto:true},
    {id:'chapter',name:'章节开场',use:'长文分节、新闻、观点',description:'细金线先画出轮廓，再让本节标题落定。',duration:4,auto:true,probe:'primary'},
    {id:'highlight',name:'重点划线',use:'观点强调、关键问题',description:'荧光底线横向铺开，让注意力停在核心句上。',duration:5,auto:true,probe:'primary'},
    {id:'quote',name:'引文显影',use:'采访、金句、评论',description:'文字像翻开的一页逐行显现，最后保留完整句子。',duration:6,auto:true,probe:'primary'},
    {id:'steps',name:'步骤接力',use:'教程概览、操作顺序',description:'流程节点依次强调；实际步骤与截图始终留在正文。',duration:8,auto:true,probe:'primary'},
    {id:'timeline',name:'时间展开',use:'事件梳理、产品迭代',description:'时间轴向下生长，已有事件依次出现。',duration:7,auto:true,probe:'primary'},
    {id:'comparison',name:'双栏对照',use:'模型比较、方案选择',description:'两个观点先后到位，最终同时可见，方便对照。',duration:6,auto:true,probe:'primary'},
    {id:'focus',name:'画面聚焦',use:'截图细节、界面讲解',description:'保持原图，移动轻描边提示观察区域，不改原始像素。',duration:8,auto:true,probe:'primary',image:true},
    {id:'panorama',name:'横幅漫游',use:'场景、作品、视觉案例',description:'画面缓慢平移；完整原图仍应放在相邻正文中。',duration:12,auto:true,probe:'primary',image:true},
    {id:'caption',name:'图文入场',use:'图片讲解、场景引入',description:'画面先出现，简短说明随后显影。',duration:6,auto:true,probe:'primary',image:true},
    {id:'path',name:'路径生长',use:'决策流程、方法拆解',description:'路线逐段连接，让读者看清步骤之间的关系。',duration:8,auto:true,probe:'primary'},
    {id:'notebook',name:'手记落笔',use:'心得、复盘、文学随笔',description:'纸笺上的句子随笔划展开，朱砂小印最后落定。',duration:6,auto:true,probe:'primary'},
    {id:'conclusion',name:'结论收束',use:'文章结尾、阶段小结',description:'重点分层显影，收成一个简洁的结束画面。',duration:5,auto:true,probe:'primary'},
    {id:'cards',name:'卡片递进',use:'三个发现、案例摘要',description:'三张纸卡依次入场，最终完整并列。',duration:7,auto:true,probe:'primary'},
    {id:'reveal',name:'问题翻面',use:'问答、误区、悬念揭晓',description:'点按问题封面揭晓答案；静态版本直接展示两者。',duration:3,auto:false,probe:'primary'}
  ];
  const images={cinema:'backgrounds/cinema.png',ink:'backgrounds/ink.png',...(window.MotionAssetURLs||{})};
  const ready=Promise.all(Object.keys(images).map(async name=>{if(images[name].startsWith('data:'))return;const response=await fetch(images[name]);if(!response.ok)throw Error('动效背景未加载');const blob=await response.blob();images[name]=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob)})}));
  const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  function make(kind,options={}){
    const p=options.prefix||'wxMotion'+Math.random().toString(36).slice(2,10),moving=options.animate!==false,entry=catalog.find(x=>x.id===kind);if(!entry)throw Error('未知动效');
    const c=options.content||{},short=(value,n=14)=>Array.from(String(value)).slice(0,n).join('')+(Array.from(String(value)).length>n?'…':''),title=c.title||'先拆问题，再找答案',label=c.label||'FIRST PRINCIPLES',parts=Array.from(c.title||'拆掉默认答案才看得到本质'),split=parts.length<=11?parts.length:Math.min(14,Math.ceil(parts.length/2)),lines=c.lines||[parts.slice(0,split).join(''),parts.slice(split,split+14).join('')],items=(c.items||(options.content?[title,c.subtitle||label,'继续阅读全文']:['明确目标','区分前提','做小验证'])).slice(0,4);
    const serif='Songti SC,SimSun,serif',sans='Microsoft YaHei,PingFang SC,sans-serif';
    const text=(x,y,value,size=30,color='#ffffff',extra='',font=sans)=>`<text x="${x}" y="${y}" fill="${color}" font-size="${size}" style="font-family:${font}!important" ${extra}>${escape(value)}</text>`;
    const begin=`0s;${p}Root.click`,repeat=options.loop===false?'1':'indefinite';
    const a=(name,values,dur,keys,extra='',trigger=begin)=>moving?`<animate attributeName="${name}" values="${values}" dur="${dur}s" ${keys?`keyTimes="${keys}"`:''} begin="${trigger}" repeatCount="${repeat}" fill="freeze" ${extra}/>`:'';
    const translate=(values,dur,keys,trigger=begin,loop=repeat)=>moving?`<animateTransform attributeName="transform" type="translate" values="${values}" dur="${dur}s" keyTimes="${keys}" begin="${trigger}" repeatCount="${loop}" fill="freeze" calcMode="spline" keySplines="${keys.split(';').slice(1).map(()=>'.22 .8 .25 1').join(';')}"/>`:'';
    const image=(name,x=0,y=0,width=720,height=450)=>`<image xlink:href="${escape(c.image||images[name])}" x="${x}" y="${y}" width="${width}" height="${height}" preserveAspectRatio="xMidYMid slice"/>`;
    const root=(content,height=450)=>{
      if(options.content&&['cinema','fold','carousel','constellation','ink','wipe'].includes(kind)){
        const replacements={'FIRST PRINCIPLES':short(label,26),'默认答案':short(c.before_label||label,18),'拆掉默认答案':short(lines[0]||title,11),'才看得到本质':short(lines[1]||label,11),'先拆问题，再用 AI。':short(c.subtitle||label,20),'从经验，走向证据':short(label,18),'IDEAS  /  FIRST PRINCIPLES':'READ / IDEAS',
          '拆解之后，才有新答案':short(label,22),'别急着找工具。':short(lines[0]||title,13),'先问，结果是什么？':short(lines[1]||c.subtitle||title,13),'第一性原理 · 从目标重新开始':short(c.subtitle||label,25),'给一个问题，打开另一种答案':short(title,22),
          '把喧哗放远，':short(lines[0]||title,13),'把问题看清。':short(lines[1]||label,13),'跳出经验，回到本质。':short(c.subtitle||label,22),'格物 · 见本质':short(label,16),'格物':short(label,2),
          '想清结果':short(items[0],5),'拆开假设':short(items[1]||items[0],5),'做小验证':short(items[2]||items[0],5),'思考的三个动作':short(title,20),'不是“用什么 AI”':short(c.subtitle||label,17),'而是“我需要什么结果”':short(items[0],17),'把事实、约束和假设':short(items[1]||items[0],17),'放在不同的位置':short(label,17),'先验证最关键的一步':short(items[2]||items[0],17),'再决定要不要继续':short(label,17),
          '让判断，形成自己的路径':short(title,23),'区分前提，再做最小验证':short(c.subtitle||label,23),'问题':short(c.center||title,4),'事实':short(items[0],4),'约束':short(items[1]||items[0],4),'假设':short(items[2]||items[0],4),'验证':short(items[3]||'下一步',4),
          '从工具出发':short(c.before_label||'问题',12),'用哪个 AI？':short(c.before||title,9),'功能很多，却不知道先做什么。':short(c.before_note||label,23),'从目标出发':short(c.after_label||'换个角度',12),'要解决':short(lines[0]||title,9),'什么问题？':short(lines[1]||c.after||label,9),'先问结果，再选工具。':short(c.subtitle||label,20),'第一性原理':short(label,14)};
        content=content.replace(/(<text\b[^>]*>)([^<]*)(<\/text>)/g,(all,start,value,end)=>start+(Object.hasOwn(replacements,value)?escape(replacements[value]):value)+end);
      }
      return `<svg id="${p}Root" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 720 ${height}" width="100%" height="${height}" role="img" aria-label="动效示例：${entry.name}" style="display:block;width:100%;height:auto;max-width:100%;overflow:hidden;cursor:${moving?'pointer':'default'}">${content}</svg>`;
    };
    const frame=(color='#d6b675')=>`<rect x="18" y="18" width="684" height="414" rx="3" fill="none" stroke="${color}" stroke-opacity=".5"/>`;
    const paper='<rect width="720" height="450" fill="#f3efe3"/>',dark='<rect width="720" height="450" fill="#142c31"/>',fade=(delay=.1,dur=6)=>a('opacity','0;0;1;1',dur,`0;${delay};${Math.min(delay+.25,.95)};1`),revealWidth=(width,dur=5)=>a('width',`0;${width};${width}`,dur,'0;.65;1');
    if(kind==='chapter')return root(`<rect width="720" height="185" fill="#f2f4ef"/><path d="M32 22 H688 V163 H32 Z" stroke="#a0b39c" fill="none" pathLength="100" stroke-dasharray="100" stroke-dashoffset="0" data-motion-probe="primary">${a('stroke-dashoffset','100;0;0',4,'0;.55;1')}</path>${text(52,68,short(label,24),20,'#73846b','letter-spacing="2"')}<g>${fade(.14,4)}${text(52,126,short(title,19),34,'#28453c','font-weight="700"',serif)}</g>`,185);
    if(kind==='highlight')return root(`<rect width="720" height="240" fill="#fffdf5"/>${text(40,49,short(label,28),19,'#7f8060')}<rect x="39" y="128" width="630" height="36" rx="3" fill="#e0dc99" data-motion-probe="primary">${revealWidth(630,5)}</rect>${text(40,131,short(title,19),34,'#364039','font-weight="700"',serif)}<path d="M40 193 H680" stroke="#d1d4c2"/>`,240);
    if(kind==='quote')return root(`${paper}${text(42,102,'“',105,'#a59973','',serif)}<defs><clipPath id="${p}Quote"><rect x="102" y="100" width="552" height="235" data-motion-probe="primary">${revealWidth(552,6)}</rect></clipPath></defs><g clip-path="url(#${p}Quote)">${text(105,178,short(lines[0]||title,15),37,'#393d32','',serif)}${text(105,245,short(lines[1]||c.subtitle||label,15),37,'#393d32','',serif)}</g><path d="M105 306 H650" stroke="#a59973"/>${text(105,355,short(label,27),20,'#79795f','',serif)}`);
    if(kind==='steps'||kind==='path'){const nodes=items.length?items:['开始','继续','完成'];return root(`${dark}${text(40,57,short(title,23),29,'#efeadb','',serif)}<path d="M85 202 H630" fill="none" stroke="#6e9c8e" stroke-width="2" pathLength="100" stroke-dasharray="100" stroke-dashoffset="0" data-motion-probe="primary">${a('stroke-dashoffset','100;0;0',8,'0;.7;1')}</path>${nodes.map((item,i)=>{const x=85+i*545/Math.max(1,nodes.length-1);return `<circle cx="${x}" cy="202" r="29" fill="#213d3e" stroke="#a9c5ac"/><circle cx="${x}" cy="202" r="38" fill="none" stroke="#e3d7a8" opacity=".14">${a('opacity','0.14;1;0.14;0.14',8,`0;${.15+i*.16};${.28+i*.16};1`)}</circle>${text(x,211,String(i+1),24,'#eee2b6','text-anchor="middle"')}${text(x,280,short(item,7),22,'#d8e8da','text-anchor="middle"')}`}).join('')}${text(360,381,short(c.subtitle||label,26),22,'#a4bdb3','text-anchor="middle"',serif)}`);}
    if(kind==='timeline')return root(`${paper}${text(43,54,short(title,23),29,'#343f36','',serif)}<path d="M81 104 V375" stroke="#a59165" stroke-width="2" pathLength="100" stroke-dasharray="100" stroke-dashoffset="0" data-motion-probe="primary">${a('stroke-dashoffset','100;0;0',7,'0;.78;1')}</path>${items.slice(0,3).map((item,i)=>`<g>${fade(.07+i*.19,7)}<circle cx="81" cy="${133+i*103}" r="7" fill="#a59165"/>${text(116,142+i*103,short(item,19),28,'#3b4839','',serif)}${text(116,175+i*103,short((c.notes||[])[i]||'阅读正文中的完整说明',27),18,'#7b806b')}</g>`).join('')}`);
    if(kind==='comparison')return root(`<rect width="720" height="450" fill="#f0eee4"/>${text(40,54,short(title,24),28,'#354939','',serif)}${[0,1].map((i)=>`<g data-motion-probe="${i===0?'primary':'secondary'}" transform="translate(0 0)">${translate(i===0?'-350 0;0 0;0 0':'350 0;0 0;0 0',6,'0;.4;1')}<rect x="${32+i*340}" y="91" width="322" height="314" rx="4" fill="${i===0?'#dce5dd':'#dce4eb'}"/>${text(54+i*340,147,short((c.labels||['角度一','角度二'])[i],10),23,i===0?'#49634e':'#3e5974')}${text(54+i*340,219,short((c.items||['先看问题','再看证据'])[i],8),34,'#283e36','font-weight="700"',serif)}${text(54+i*340,302,short((c.notes||[label,label])[i],14),20,'#6b7663')}</g>`).join('')}`);
    if(kind==='focus')return root(`<rect width="720" height="450" fill="#0e2531"/>${image('cinema',24,24,672,352)}<rect x="60" y="68" width="210" height="182" fill="none" stroke="#f7df9f" stroke-width="3" data-motion-probe="primary">${a('x','60;390;60',8,'0;.5;1')}</rect><rect x="27" y="378" width="666" height="58" fill="#0e2531"/>${text(45,414,short(title,25),25,'#efead9','',serif)}`);
    if(kind==='panorama')return root(`<g transform="translate(0 0)" data-motion-probe="primary">${translate('0 0;-90 0;0 0',12,'0;.5;1')}${image('cinema',0,0,840,450)}</g><rect x="0" y="345" width="720" height="105" fill="#101f29" opacity=".8"/>${text(36,398,short(title,24),30,'#f5ead1','',serif)}`);
    if(kind==='caption')return root(`${paper}<g opacity="1" data-motion-probe="primary">${fade(.02,6)}${image('ink',26,22,668,290)}</g><g>${fade(.35,6)}${text(37,366,short(title,23),31,'#3e4b3d','',serif)}${text(37,410,short(c.subtitle||label,30),19,'#7c8268')}</g>`);
    if(kind==='notebook')return root(`${paper}${Array.from({length:7},(_,i)=>`<path d="M38 ${80+i*48} H682" stroke="#d8d1bc"/>`).join('')}<path d="M80 35 V414" stroke="#c48670" opacity=".55"/><defs><clipPath id="${p}Pen"><rect x="99" y="81" width="562" height="217" data-motion-probe="primary">${revealWidth(562,6)}</rect></clipPath></defs><g clip-path="url(#${p}Pen)">${text(105,157,short(lines[0]||title,14),35,'#514438','',serif)}${text(105,253,short(lines[1]||label,14),35,'#514438','',serif)}</g><g>${fade(.6,6)}<rect x="578" y="340" width="65" height="65" fill="#9c3f35"/>${text(610,384,'记',35,'#f7ead1','text-anchor="middle"',serif)}</g>`);
    if(kind==='conclusion')return root(`<rect width="720" height="300" fill="#203c36"/><path d="M35 28 H685 V273 H35 Z" fill="none" stroke="#bfb17d" opacity=".7"/>${text(360,76,short(label,25),20,'#bbcaad','text-anchor="middle" letter-spacing="3"')}<g opacity="1" data-motion-probe="primary">${fade(.07,5)}${text(360,151,short(lines[0]||title,19),35,'#f3e8cf','text-anchor="middle"',serif)}${text(360,211,short(lines[1]||c.subtitle||'继续阅读，形成自己的判断',23),23,'#d9dfc9','text-anchor="middle"',serif)}</g>`,300);
    if(kind==='cards')return root(`${paper}${text(37,55,short(title,24),27,'#45563e','',serif)}${items.slice(0,3).map((item,i)=>`<g transform="translate(0 0)" data-motion-probe="${i===0?'primary':'card'+i}">${translate(`0 ${180+i*70};0 0;0 0`,7,`0;${.3+i*.16};1`)}<rect x="${25+i*230}" y="106" width="214" height="290" rx="5" fill="${['#dbe5d5','#dae3e8','#e9decf'][i]}" stroke="#c0c9b4"/>${text(46+i*230,158,'0'+(i+1),30,'#788465','font-weight="700"')}${text(46+i*230,238,short(item,7),26,'#354b3b','font-weight="700"',serif)}${text(46+i*230,338,short((c.notes||[])[i]||'详见正文',9),19,'#778065')}</g>`).join('')}`);
    if(kind==='reveal')return root(`${paper}${text(38,62,short(label,28),21,'#8a7658')}${text(38,160,short(title,18),36,'#3d4b37','',serif)}${text(38,240,short(c.answer||c.subtitle||'把完整答案放回正文中理解',23),26,'#816740','',serif)}${moving?`<g transform="translate(0 0)" data-motion-probe="primary">${translate('0 0;720 0',1.5,'0;1',`${p}Root.click`,'1')}<rect width="720" height="450" fill="#314c54"/>${text(42,78,'带着问题往下读',22,'#b6d0c9')}${text(42,181,short(c.question||title,18),37,'#f0e5c5','',serif)}<path d="M43 275 H660" stroke="#849c91"/>${text(42,342,'点按画面，揭晓这一句',25,'#d7e0ca','',serif)}</g>`:''}`);
    if(kind==='cinema')return root(`
      <defs><linearGradient id="${p}Dark"><stop stop-color="#030b15" stop-opacity=".88"/><stop offset=".7" stop-color="#030b15" stop-opacity=".1"/></linearGradient></defs>
      <g data-motion-probe="camera">${moving?`<animateTransform attributeName="transform" type="scale" values="1;1.04;1" dur="18s" begin="${begin}" repeatCount="${repeat}"/>`:''}${image('cinema')}</g>
      <rect width="720" height="450" fill="url(#${p}Dark)"/>
      ${text(48,67,'IDEAS  /  FIRST PRINCIPLES',17,'#d6b675','letter-spacing="3"')}
      <g>${text(48,170,'拆掉默认答案',56,'#f4e8c9','font-weight="600"',serif)}${text(48,234,'才看得到本质',56,'#f4e8c9','font-weight="600"',serif)}${moving?a('opacity','0;0;1;1;1',9,'0;.1;.26;.82;1'):''}</g>
      <path d="M48 273 H308" stroke="#b89458" stroke-width="1.5"/>
      <g>${text(48,318,'先拆问题，再用 AI。',27,'#f0ece2','',serif)}${a('opacity','0;0;1;1',9,'0;.24;.42;1')}</g>
      ${text(48,395,'从经验，走向证据',19,'#cfc0a2','letter-spacing="2"',serif)}
      <rect data-motion-probe="curtain" x="720" width="720" height="450" fill="#06101c">${a('x','0;0;720;720',9,'0;.05;.3;1','calcMode="spline" keySplines=".22 .8 .25 1;.22 .8 .25 1;.22 .8 .25 1"')}</rect>${frame()}`);
    if(kind==='fold')return root(`
      <rect width="720" height="450" fill="#f6f0e4"/><rect x="35" y="30" width="650" height="390" fill="#fffaf0" stroke="#c8b69a"/>
      <path d="M62 77 H658 M62 372 H658" stroke="#b89c6e" stroke-width="1"/>
      ${text(360,117,'拆解之后，才有新答案',23,'#906443','text-anchor="middle" letter-spacing="4"',serif)}
      ${text(360,204,'别急着找工具。',49,'#382f2a','text-anchor="middle"',serif)}${text(360,275,'先问，结果是什么？',46,'#9c3b36','text-anchor="middle"',serif)}
      ${text(360,340,'第一性原理 · 从目标重新开始',21,'#7b6a55','text-anchor="middle"',serif)}
      ${moving?`<g transform="translate(0 0)" data-motion-probe="fold">${translate('0 0;0 -470',1.5,'0;1',`${p}Root.click`,'1')}
        <rect width="720" height="450" fill="#8e302f"/><path d="M0 0 L360 238 L720 0 M0 450 L286 209 M720 450 L434 209" fill="none" stroke="#c68e76" stroke-width="1.5"/>
        <circle cx="360" cy="235" r="57" fill="#ead7b1" stroke="#ccb57f" stroke-width="3"/>${text(360,253,'启',51,'#883731','text-anchor="middle"',serif)}
        ${text(360,102,'给一个问题，打开另一种答案',28,'#f6e6ce','text-anchor="middle"',serif)}${text(360,380,'点按封页 · 揭晓',23,'#edd6b6','text-anchor="middle" letter-spacing="3"',serif)}
      </g>`:''}`);
    if(kind==='carousel'){
      const slides=[{color:'#eaf2ec',ink:'#26473a',step:'01',title:'想清结果',lines:['不是“用什么 AI”','而是“我需要什么结果”'],icon:'M474 158 H627 V287 H474 Z M502 191 H599 M502 221 H571 M502 251 H584'},
        {color:'#eaf0f7',ink:'#244563',step:'02',title:'拆开假设',lines:['把事实、约束和假设','放在不同的位置'],icon:'M479 174 L549 134 L619 174 L549 214 Z M479 211 L549 251 L619 211 M479 248 L549 288 L619 248'},
        {color:'#f6ece1',ink:'#825439',step:'03',title:'做小验证',lines:['先验证最关键的一步','再决定要不要继续'],icon:'M497 152 H608 V280 H497 Z M522 187 L534 199 L560 174 M522 235 H579'}];
      const content=slides.map((s,i)=>`<g transform="translate(${i*720} 0)"><rect width="720" height="450" fill="${s.color}"/>${text(44,65,'思考的三个动作',19,s.ink,'letter-spacing="3"')}${text(41,151,s.step,66,s.ink,'font-weight="700"')}${text(44,222,s.title,53,s.ink,'font-weight="600"')}${text(44,285,s.lines[0],24,s.ink)}${text(44,323,s.lines[1],24,s.ink)}<path d="${s.icon}" stroke="${s.ink}" stroke-width="2.5" fill="none"/><line x1="44" y1="375" x2="676" y2="375" stroke="${s.ink}" stroke-opacity=".3"/>${text(44,412,'FIRST PRINCIPLES',17,s.ink,'letter-spacing="3"')}${text(660,412,s.step+' / 03',18,s.ink,'text-anchor="end"')}</g>`).join('');
      if(!moving)return root(`<rect width="720" height="450" fill="#f0f3ee"/>${text(42,66,'思考的三个动作',22,'#26473a')} ${slides.map((s,i)=>`<rect x="${32+i*228}" y="101" width="216" height="297" rx="8" fill="${s.color}"/>${text(52+i*228,160,s.step,36,s.ink,'font-weight="700"')}${text(52+i*228,221,s.title,30,s.ink,'font-weight="700"')}${text(52+i*228,283,['明确目标','分类前提','验证关键'][i],22,s.ink)}`).join('')}`);
      return root(`<g transform="translate(0 0)" data-motion-probe="carousel">${translate('0 0;0 0;-720 0;-720 0;-1440 0;-1440 0;0 0',12,'0;.22;.3;.55;.63;.9;1')}${content}</g>`);
    }
    if(kind==='constellation'){
      const nodes=[{x:116,y:147,name:'事实'},{x:604,y:147,name:'约束'},{x:116,y:298,name:'假设'},{x:604,y:298,name:'验证'}];
      return root(`<defs><radialGradient id="${p}Space"><stop stop-color="#163c4c"/><stop offset="1" stop-color="#060f20"/></radialGradient><radialGradient id="${p}Glow"><stop stop-color="#8be3d5" stop-opacity=".7"/><stop offset="1" stop-color="#8be3d5" stop-opacity="0"/></radialGradient></defs>
        <rect width="720" height="450" fill="url(#${p}Space)"/>
        ${Array.from({length:32},(_,i)=>`<circle cx="${(i*127+33)%700}" cy="${(i*83+19)%430}" r="${i%3===0?1.8:1}" fill="#d0e1f0" opacity="${.18+(i%4)*.1}"/>`).join('')}
        ${text(360,58,'让判断，形成自己的路径',27,'#e5eadf','text-anchor="middle"',serif)}
        <ellipse cx="360" cy="225" rx="236" ry="122" fill="none" stroke="#61979c" stroke-opacity=".24" stroke-width="1"/>
        <g>${nodes.map((n,i)=>`<path d="M360 225 Q${n.x} 225 ${n.x} ${n.y}" fill="none" stroke="#74cbbd" stroke-width="1.5" pathLength="100" stroke-dasharray="100" stroke-dashoffset="0">${a('stroke-dashoffset','100;0;0;100',8,'0;.22;.88;1')}</path>`).join('')}</g>
        <circle cx="360" cy="225" r="100" fill="url(#${p}Glow)"/>
        <circle cx="360" cy="225" r="57" fill="#102432" stroke="#dccb9c" stroke-width="1.5"/>${text(360,236,'问题',31,'#f0e0b5','text-anchor="middle"',serif)}
        ${nodes.map((n,i)=>`<circle cx="${n.x}" cy="${n.y}" r="39" fill="#112a39" stroke="#83c5be" stroke-width="1"/>${text(n.x,n.y+10,n.name,28,'#e8f2ec','text-anchor="middle"',serif)}`).join('')}
        <g data-motion-probe="orbit" transform="translate(0 0)">${moving?`<animateTransform attributeName="transform" type="rotate" values="0 360 225;360 360 225" dur="16s" begin="${begin}" repeatCount="${repeat}"/>`:''}<circle cx="360" cy="105" r="7" fill="#efdaaa"/><circle cx="360" cy="105" r="16" fill="#efdaaa" opacity=".13"/></g>
        ${text(360,411,'区分前提，再做最小验证',24,'#bdcfcc','text-anchor="middle"',serif)}`);
    }
    if(kind==='ink')return root(`<rect width="720" height="450" fill="#f1e6d0"/>
      <g data-motion-probe="pan" transform="translate(0 0)">${translate('0 0;-24 0;0 0',24,'0;.5;1')}${image('ink',0,0,760,450)}</g>
      <rect x="0" y="0" width="380" height="450" fill="#f5ecd8" fill-opacity=".38"/>
      ${text(53,76,'格物 · 见本质',22,'#746553','letter-spacing="6"',serif)}
      <g>${text(52,166,'把喧哗放远，',46,'#39382f','',serif)}${text(52,235,'把问题看清。',46,'#39382f','',serif)}${a('opacity','0;0;1;1',12,'0;.18;.32;1')}</g>
      <path d="M53 284 H314" stroke="#8d6e42" stroke-width="1"/>${text(53,328,'跳出经验，回到本质。',24,'#6c6250','',serif)}
      <rect x="52" y="370" width="32" height="32" fill="#9b3d32"/>${text(68,392,'思',21,'#f8ead5','text-anchor="middle"',serif)}
      <g data-motion-probe="scroll" transform="translate(-380 0)">${translate('0 0;0 0;-380 0;-380 0',12,'0;.03;.23;1')}<rect width="360" height="450" fill="#efe2c6"/><path d="M342 0 V450" stroke="#8d6e42" stroke-width="9"/>${text(302,266,'格物',37,'#6c6250','writing-mode="vertical-rl"',serif)}</g>
      <g transform="translate(380 0)">${translate('0 0;0 0;380 0;380 0',12,'0;.03;.23;1')}<rect x="360" width="360" height="450" fill="#efe2c6"/><path d="M376 0 V450" stroke="#8d6e42" stroke-width="9"/></g>`);
    if(kind==='wipe')return root(`
      <defs><clipPath id="${p}Reveal"><rect width="720" height="450" data-motion-probe="wipe">${a('width','0;0;720;720;0',10,'0;.12;.4;.84;1','calcMode="spline" keySplines=".22 .8 .25 1;.22 .8 .25 1;.22 .8 .25 1;.22 .8 .25 1"')}</rect></clipPath></defs>
      <rect width="720" height="450" fill="#182c42"/>${text(45,63,'从工具出发',23,'#b7c9d8')}${text(45,180,'用哪个 AI？',66,'#f1f5f5','font-weight="700"')}${text(45,258,'功能很多，却不知道先做什么。',27,'#c0d0db')}${text(45,402,'默认答案',22,'#b7c9d8','letter-spacing="3"')}
      <g clip-path="url(#${p}Reveal)"><rect width="720" height="450" fill="#ece9da"/><path d="M444 0 L720 170 V450 H555 L373 234 Z" fill="#d4dcc7"/><path d="M577 0 L720 86 V350 L517 165 Z" fill="#b5c4ab"/>
        ${text(45,63,moving?'从目标出发':'从“用哪个 AI” → 从目标出发',23,'#63724f')}${text(45,172,'要解决',62,'#304434','font-weight="700"')}${text(45,247,'什么问题？',62,'#304434','font-weight="700"')}${text(45,319,'先问结果，再选工具。',29,'#627251')}${text(45,402,'第一性原理',22,'#63724f','letter-spacing="3"')}
      </g>`);
  }
  return {catalog,ready,make};
})();
