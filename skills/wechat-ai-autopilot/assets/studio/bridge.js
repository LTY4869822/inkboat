    // Keep Zhouxing as the actual formatter; augment only our motion modules.
    const context=window.StudioContext||{}, initialPlan=context.plan||{enabled:true,items:[]};
    let studioPlan=JSON.parse(JSON.stringify(initialPlan));
    let studioTheme=null;
    const originalSetTheme=setTheme;
    setTheme=function(id){studioTheme=null;originalSetTheme(id)};
    const studioRender=render;
    function studioUpdateMotion(staticOnly=false){
      article.querySelectorAll('[data-studio-motion]').forEach(n=>n.remove());
      studioPlan.items.forEach(item=>{
        const anchor=article.querySelectorAll(item.anchor.type)[item.anchor.index];if(!anchor)return;
        const section=document.createElement('section');section.dataset.studioMotion=item.id;section.setAttribute('aria-hidden','true');section.style.cssText='margin:18px 0 24px;max-width:100%';
        section.innerHTML=MotionDesigns.make(item.kind,{prefix:'wx'+item.id,content:item.content,animate:!staticOnly&&studioPlan.enabled&&!matchMedia('(prefers-reduced-motion: reduce)').matches,loop:false});anchor.after(section);
      });
    }
    render=function(){studioRender();studioUpdateMotion()};
    const originalClone=makeClipboardClone;
    makeClipboardClone=function(){const clone=originalClone(),originals=[...article.querySelectorAll('[data-studio-motion] svg')],targets=[...clone.querySelectorAll('svg')];originals.forEach((original,index)=>{const target=targets[index];if(!target)return;const svg=original.cloneNode(true);[svg,...svg.querySelectorAll('*')].forEach(n=>[...n.attributes].filter(a=>a.name.startsWith('data-')).forEach(a=>n.removeAttribute(a.name)));target.replaceWith(svg)});return clone};
    function snapshot(){return {schema_version:2,baseThemeId:activeTheme.id,themeOverride:studioTheme?copyData(studioTheme):null,accent:currentAccent,font:fontSelect.value,typeOverrides:copyData(typeOverrides),styleSelections:copyData(styleSelections),spacingOverrides:spacingOverrides?copyData(spacingOverrides):null,motion:copyData(studioPlan)}}
    function apply(raw){
      const safe=sanitizePreset({...raw,id:'studio-session',name:'当前文章'});if(!safe)throw Error('排版设置无效');
      setTheme(safe.baseThemeId);currentAccent=safe.accent;accentColor.value=currentAccent;accentHex.value=currentAccent;fontSelect.value=safe.font;
      if(raw.themeOverride&&typeof raw.themeOverride.css==='string'){studioTheme=copyData(raw.themeOverride);activeTheme={...activeTheme,...studioTheme,id:safe.baseThemeId}}
      typeOverrides=copyData(safe.typeOverrides);styleSelections=copyData(safe.styleSelections);spacingOverrides=safe.spacingOverrides?copyData(safe.spacingOverrides):null;
      if(raw.motion&&typeof raw.motion==='object')studioPlan=copyData(raw.motion);
      updateFlowPalette();syncStyleOptions();render();syncAllCustomSelects();if(spacingOverrides){spacingIds.forEach(id=>spacingInputs[id].value=spacingOverrides[id]);updateSpacingOutputs()}
      return snapshot();
    }
    function exportHTML(staticOnly=false){
      const clone=stripClipboardMetadata(makeClipboardClone());if(staticOnly){[...clone.querySelectorAll('svg')].forEach((svg,index)=>{const item=studioPlan.items[index];if(!item)return;const holder=document.createElement('div');holder.innerHTML=MotionDesigns.make(item.kind,{prefix:'wxStatic'+item.id,content:item.content,animate:false});const replacement=holder.firstElementChild;replacement.querySelectorAll('*').forEach(n=>[...n.attributes].filter(a=>a.name.startsWith('data-')).forEach(a=>n.removeAttribute(a.name)));svg.replaceWith(replacement)})}return clone.outerHTML;
    }
    window.studioBridge={
      ready:MotionDesigns.ready,
      catalog:()=>({themes:themes.map(({id,name,description,accent})=>({id,name,description,accent})),fonts:fontChoices,headings:headingOptions(),quotes:optionsForStyleTarget('quote'),images:optionsForStyleTarget('image'),motions:MotionDesigns.catalog}),
      snapshot,apply,
      setTheme:id=>{const font=fontSelect.value;setTheme(id);fontSelect.value=font;render()},
      setEnabled:value=>{studioPlan.enabled=!!value;studioUpdateMotion()},
      recommendMotion:()=>{studioPlan=copyData(initialPlan);studioUpdateMotion()},
      setMotion:(kind,id)=>{const item=studioPlan.items.find(x=>x.id===id)||studioPlan.items[0];if(item){item.kind=kind;studioUpdateMotion()}},
      addMotion:(kind,chapter=0)=>{const h=article.querySelectorAll('h2')[chapter]||article.querySelector('h1');if(!h)return;const text=h.cloneNode(true);text.querySelectorAll('[aria-hidden]').forEach(n=>n.remove());const id='m'+Math.random().toString(36).slice(2,10);studioPlan.items.push({id,kind,anchor:{type:h.tagName.toLowerCase(),index:h.tagName==='H2'?chapter:0},content:{title:text.textContent.trim(),label:'本节重点'},reason:'用户在工坊中为本节选择的动效表达'});studioPlan.enabled=true;studioUpdateMotion();return id},
      removeMotion:id=>{studioPlan.items=studioPlan.items.filter(x=>x.id!==id);if(!studioPlan.items.length)studioPlan.enabled=false;studioUpdateMotion()},
      replay:studioUpdateMotion,exportHTML,
      exportTheme:(id,name)=>({...activeTheme,id,name,description:`基于${activeTheme.name}的个人原创调整`,default:false,order:200,accent:currentAccent,css:[...themeStyle.sheet.cssRules].flatMap(rule=>rule.type===CSSRule.STYLE_RULE?[rule.cssText]:(rule.type===CSSRule.MEDIA_RULE&&matchMedia(rule.conditionText).matches?[...rule.cssRules].map(r=>r.cssText):[])).join('\n'),evidence:{source_type:'original',source:'用户在周行工坊中保存的设计',observed:['周行实际渲染的当前主题与组件'],inferred:[],unobserved:['微信后台及真机需按文章验收'],confidence:'medium'}}),
      copy:()=>copyButton.click(),
      scrollToMotion:id=>article.querySelector(`[data-studio-motion="${id||studioPlan.items[0]?.id}"]`)?.scrollIntoView({behavior:'smooth',block:'center'}),
      scrollToChapter:index=>article.querySelectorAll('h2')[index]?.scrollIntoView({behavior:'smooth',block:'start'}),
      text:()=>{const clone=article.cloneNode(true);clone.querySelectorAll('[aria-hidden="true"],[data-studio-motion]').forEach(n=>n.remove());return clone.textContent},
      chapters:()=>[...article.querySelectorAll('h2')].map(h=>{const clone=h.cloneNode(true);clone.querySelectorAll('[aria-hidden="true"]').forEach(n=>n.remove());return clone.textContent.trim()}),
      sourceHash:()=>context.article_sha256
    };
    MotionDesigns.ready.then(()=>studioUpdateMotion()).catch(()=>{status.className='status error';status.textContent='动效图片加载失败，请刷新后保存。'});
