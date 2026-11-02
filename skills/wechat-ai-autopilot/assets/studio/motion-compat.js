// Local preview compiler mirrors motion_transport.py's four verified variants.
// Never applies to an approved historical revision or the WeChat editor DOM.
(()=>{
  const original=MotionDesigns.make,stable=['quote','steps','comparison','conclusion'];
  MotionDesigns.catalog.forEach(x=>x.wechatVerified=stable.includes(x.id));
  MotionDesigns.make=(kind,options={})=>{
    const source=original(kind,options);
    if(options.animate===false||options.loop!==false||!stable.includes(kind))return source;
    const svg=new DOMParser().parseFromString(source,'image/svg+xml').documentElement;
    const ns='http://www.w3.org/2000/svg',trigger='0s;click;touchstart';
    const el=(tag,attrs={})=>{const n=svg.ownerDocument.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));return n};
    const anim=(tag,attrs)=>el(tag,{begin:trigger,restart:'whenNotActive',repeatCount:'1',fill:'freeze',...attrs});
    const height=svg.getAttribute('viewBox').split(' ')[3];
    const hit=()=>el('rect',{x:-1000,y:0,width:2700,height,fill:'transparent','pointer-events':'all'});
    const animations=()=>[...svg.querySelectorAll('animate,animateTransform')];
    if(kind==='steps'&&[...svg.children].filter(x=>x.tagName==='circle'&&x.getAttribute('r')==='38').length!==3)return source;
    if(kind==='quote'){
      svg.querySelectorAll('defs').forEach(n=>n.remove());svg.querySelectorAll('[clip-path]').forEach(n=>n.removeAttribute('clip-path'));
      const veil=el('g',{transform:'translate(0 0)'});
      veil.append(anim('animateTransform',{attributeName:'transform',type:'translate',values:'-552 0;0 0;0 0',dur:'6s',keyTimes:'0;.65;1'}));
      veil.append(el('rect',{x:654,y:100,width:552,height:170,fill:'#f3efe3'}),hit());svg.append(veil);
    }else if(kind==='steps'){
      const group=el('g',{'stroke-dashoffset':0}),line=svg.querySelector('path[pathLength="100"]');
      const a=line.querySelector('animate').cloneNode(true);a.setAttribute('begin',trigger);a.setAttribute('restart','whenNotActive');
      animations().forEach(n=>n.remove());line.removeAttribute('stroke-dashoffset');group.append(a);
      const children=[...svg.children],rings=children.filter(n=>n.tagName==='circle'&&n.getAttribute('r')==='38');children.forEach(n=>group.append(n));
      const xs=rings.map(n=>Number(n.getAttribute('cx'))),halo=el('g',{transform:'translate(0 0)',opacity:0});
      halo.append(anim('animateTransform',{attributeName:'transform',type:'translate',values:`0 0;0 0;${xs[1]-xs[0]} 0;${xs[1]-xs[0]} 0;${xs[2]-xs[0]} 0;${xs[2]-xs[0]} 0`,dur:'8s',keyTimes:'0;.16;.29;.46;.59;1'}));
      halo.append(anim('animate',{attributeName:'opacity',values:'0;1;1;1;1;0;0',dur:'8s',keyTimes:'0;.04;.16;.29;.46;.65;1'}));
      halo.append(el('circle',{cx:xs[0],cy:202,r:38,fill:'none',stroke:'#e3d7a8'}),hit());group.append(halo);svg.append(group);
    }else if(kind==='comparison'){
      const [left,right]=[...svg.children].filter(n=>n.tagName==='g');
      right.querySelector('animateTransform').setAttribute('values','700 0;0 0;0 0');
      animations().forEach(n=>{n.setAttribute('begin',trigger);n.setAttribute('restart','whenNotActive')});right.append(hit());left.append(right);
    }else if(kind==='conclusion'){
      animations().forEach(n=>{n.setAttribute('begin',trigger);n.setAttribute('restart','whenNotActive')});svg.querySelector('g').append(hit());
    }
    svg.removeAttribute('id');svg.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
    return new XMLSerializer().serializeToString(svg);
  };
})();
