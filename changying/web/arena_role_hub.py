"""三科共享的教师 3 Tab 控制台（班级热力诊断 / 任务追踪 / 学生明细）与家长任务+鼓励视图（纯 ES5，无 innerHTML）."""
from __future__ import annotations

ARENA_ROLE_HUB_JS = r"""
function arenaRoleHub(role,subject){
  root.textContent='';
  var isTeacher=(role==='teacher'||role==='admin');
  var backHref=isTeacher?'/v1':'/classic?legacy=1&unified=1&page=parent';
  var backText=isTeacher?'‹ 返回工作台':'‹ 返回家长端';
  var subjLinks=el('div',{class:'ea-subj'},
    el('a',{href:'/v1/math-star-map',class:subject==='数学'?'on':'',text:'数学'}),
    el('a',{href:'/v1/english-star-map',class:subject==='英语'?'on':'',text:'英语'}),
    el('a',{href:'/v1/chinese-star-map',class:subject==='语文'?'on':'',text:'语文'}));
  var bar=el('div',{class:'ma-topbar'},
    el('div',{class:'ma-topbar-left'},el('a',{class:'ma-link-btn',href:backHref,text:backText}),subjLinks),
    el('div',{class:'ma-topbar-right'},el('span',{class:'ma-pts',text:isTeacher?('教师 · '+subject+'控制台'):('家长 · '+subject+'学情')})));
  var notice=el('div',{class:'ma-notice'});
  var body=el('div',{class:'ma-wrap'});
  var wrap=el('div',{class:'ma-wrap'},bar,notice,body);
  root.appendChild(wrap);

  function say(t,warn){
    notice.className='ma-notice'+(t?(' show '+(warn?'warn':'info')):'');
    notice.textContent=t||'';
  }
  function helperBar(txt,tag){
    var src=window.__CY_HELPER_AVATAR__||'';
    return el('div',{class:'ma-helper'},
      src?el('img',{class:'ma-helper-ava',src:src,alt:'长缨助手'}):null,
      el('div',{class:'ma-helper-body'},
        el('div',{class:'ma-helper-name',text:tag||'长缨助手'}),
        el('p',{class:'ma-helper-text',text:txt})));
  }

  /* ================= 教师端 3 Tab 控制台 ================= */
  if(isTeacher){
    var curClassId=0,curTab='heat',diagData=null,taskData=null;
    var ctrl=el('div',{class:'ma-card'}),panel=el('div',{class:'ma-wrap'});
    body.appendChild(ctrl);body.appendChild(panel);

    function dispatchTask(kind,key,goalCode,audience){
      say('正在派发任务…');
      api('/teacher/arena/tasks',{
        method:'POST',
        json:{subject:subject,class_id:curClassId,task_kind:kind,target_key:key,goal_code:goalCode,audience:audience}
      }).then(function(r){
        say('已派发《'+r.targetTitle+'》（'+r.goalLabel+'）给 '+r.assignedCount+' 名学生，截止 '+r.dueDate+'！');
        loadTasks();
      }).catch(function(e){say(e.message,true)});
    }

    function renderCtrl(){
      ctrl.textContent='';
      var sel=el('select',{class:'ma-input',style:'max-width:210px;padding:7px 10px;font-size:13.5px'});
      sel.appendChild(el('option',{value:'0',text:'全部可见学生'}));
      if(diagData&&diagData.classes){
        diagData.classes.forEach(function(c){
          var op=el('option',{value:String(c.id),text:c.name+'（'+c.grade+'年级）'});
          if(Number(c.id)===Number(curClassId))op.selected=true;
          sel.appendChild(op);
        });
      }
      sel.onchange=function(){curClassId=Number(sel.value||0);loadAll()};

      var tabs=el('div',{class:'ma-seg'});
      [['heat','薄弱热力与派发'],['tasks','任务追踪'],['students','学生明细']].forEach(function(t){
        var a=el('a',{href:'#',class:curTab===t[0]?'on':'',text:t[1]});
        a.onclick=function(e){e.preventDefault();curTab=t[0];renderCtrl();renderPanel()};
        tabs.appendChild(a);
      });

      ctrl.appendChild(el('div',{class:'ma-sum-top'},
        el('div',{},
          el('div',{class:'ma-eyebrow',text:'教—学—家三端联动 · 小学'+subject}),
          el('h2',{class:'ma-h1',text:subject+'班级诊断与任务派发'}),
          el('p',{class:'ma-sub',text:'覆盖 '+(diagData?diagData.totalNodes:0)+' 个核心考点与 '+(diagData?diagData.totalSprints:0)+' 个限时专项，当前范围 '+(diagData?diagData.studentCount:0)+' 名学生。'})),
        el('div',{class:'ma-row'},sel)));
      ctrl.appendChild(el('div',{style:'margin-top:12px'},tabs));
    }

    function renderPanel(){
      panel.textContent='';
      if(!diagData){panel.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:'正在加载班级诊断数据…'})));return}

      if(curTab==='heat'){
        panel.appendChild(helperBar('按本班未点亮和标红人数自动排序：直接点右侧「仅派薄弱生」即可精准分层布置，学生达标后系统自动验收！','长缨助手 · 精准分层建议'));
        var nCard=el('div',{class:'ma-card'},el('h3',{text:'全班考点薄弱热力榜（优先补弱）'}));
        if(!diagData.nodeHeat.length){
          nCard.appendChild(el('p',{class:'ma-sub',text:'暂无考点数据'}));
        }else{
          diagData.nodeHeat.slice(0,12).forEach(function(n){
            var gSel=el('select',{class:'ma-input',style:'width:auto;padding:5px 8px;font-size:12px'});
            gSel.appendChild(el('option',{value:'lit',text:'目标：点亮'}));
            gSel.appendChild(el('option',{value:'mastered',text:'目标：三星精通'}));
            var bWeak=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'仅派薄弱生('+n.weakCount+')'});
            bWeak.disabled=(n.weakCount<=0);
            bWeak.onclick=function(){dispatchTask('map_node',n.key,gSel.value,'weak')};
            var bAll=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'派全班'});
            bAll.disabled=(diagData.studentCount<=0);
            bAll.onclick=function(){dispatchTask('map_node',n.key,gSel.value,'all')};
            nCard.appendChild(el('div',{class:'ma-loss-row'},
              el('div',{},
                el('b',{text:n.key+' '+n.name}),
                el('div',{class:'ma-sub',text:'已点亮 '+n.litCount+'/'+diagData.studentCount+'（'+n.litRate+'%）'+(n.repairCount?' · 标红待修补 '+n.repairCount+' 人':'')})),
              el('div',{class:'ma-row'},gSel,bWeak,bAll)));
          });
        }
        panel.appendChild(nCard);

        var sCard=el('div',{class:'ma-card'},el('h3',{text:'应试专项达标率与派发'}));
        diagData.sprintHeat.forEach(function(sp){
          var sSel=el('select',{class:'ma-input',style:'width:auto;padding:5px 8px;font-size:12px'});
          sSel.appendChild(el('option',{value:'L2',text:'目标：L2 达标'}));
          sSel.appendChild(el('option',{value:'L3',text:'目标：L3 熟练'}));
          sSel.appendChild(el('option',{value:'attempt',text:'目标：完成作答'}));
          var bW=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'仅派未达标('+sp.weakCount+')'});
          bW.disabled=(sp.weakCount<=0);
          bW.onclick=function(){dispatchTask('sprint',sp.slug,sSel.value,'weak')};
          var bA=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'派全班'});
          bA.disabled=(diagData.studentCount<=0);
          bA.onclick=function(){dispatchTask('sprint',sp.slug,sSel.value,'all')};
          sCard.appendChild(el('div',{class:'ma-loss-row'},
            el('div',{},
              el('b',{text:sp.title}),
              el('div',{class:'ma-sub',text:'已达标(L2+) '+sp.passedCount+'/'+diagData.studentCount+'（'+sp.passRate+'%）· 参与 '+sp.attemptedCount+' 人'})),
            el('div',{class:'ma-row'},sSel,bW,bA)));
        });
        panel.appendChild(sCard);
        return;
      }

      if(curTab==='tasks'){
        var list=(taskData&&taskData.items)||[];
        if(!list.length){
          panel.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:'当前还没有派发过'+subject+'任务，去「薄弱热力与派发」一键布置一个吧！'})));
          return;
        }
        list.forEach(function(tk){
          var pct=tk.totalCount?Math.round(tk.doneCount/tk.totalCount*100):0;
          var closeBtn=tk.status==='active'?el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'结束任务',onclick:function(){
            api('/teacher/arena/tasks/'+tk.id+'/close',{method:'POST'}).then(function(){say('已结束任务');loadTasks()}).catch(function(e){say(e.message,true)});
          }}):el('span',{class:'ma-pill',text:'已结束'});
          panel.appendChild(el('div',{class:'ma-card'},
            el('div',{class:'ma-sum-top'},
              el('div',{},
                el('b',{text:tk.targetTitle+' · '+tk.goalLabel}),
                el('p',{class:'ma-sub',text:tk.audienceLabel+' · 截止 '+tk.dueDate+' · 达标进度 '+tk.doneCount+'/'+tk.totalCount+'（'+pct+'%）'})),
              closeBtn),
            el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})),
            tk.pendingNames&&tk.pendingNames.length
              ?el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待完成学生：'+tk.pendingNames.join('、')})
              :el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-ok);font-weight:700',text:'🎉 全员已自动达标完成！'})));
        });
        return;
      }

      /* Tab 3: 学生明细 */
      if(!diagData.students.length){
        panel.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:'当前班级暂无学生记录。'})));
        return;
      }
      diagData.students.forEach(function(it){
        var pct=it.totalNodes?Math.round(it.litNodes/it.totalNodes*100):0;
        var tierTxt=it.bestTier?(it.bestTier.code+' '+it.bestTier.name):'尚未参加专项';
        panel.appendChild(el('div',{class:'ma-card'},
          el('div',{class:'ma-sum-top'},
            el('div',{},
              el('h3',{style:'margin:0',text:it.name+(it.grade?'（'+it.grade+'年级）':'')}),
              el('p',{class:'ma-sub',style:'margin-top:3px',text:'已点亮 '+it.litNodes+'/'+it.totalNodes+'（'+pct+'%）· 精通 '+it.masteredNodes+' · 专项最高：'+tierTxt})),
            el('span',{class:'ma-pts',text:'全站积分 '+it.pointsBalance})),
          el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})),
          it.repairNames&&it.repairNames.length
            ?el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待修补考点：'+it.repairNames.join('、')})
            :el('p',{class:'ma-sub',style:'margin-top:8px',text:'当前无待修补失分点'})));
      });
    }

    function loadTasks(){
      api('/teacher/arena/tasks?subject='+encodeURIComponent(subject)+'&class_id='+curClassId).then(function(d){
        taskData=d;if(curTab==='tasks')renderPanel();
      }).catch(function(){});
    }
    function loadAll(){
      api('/teacher/arena/diagnostics?subject='+encodeURIComponent(subject)+'&class_id='+curClassId).then(function(d){
        diagData=d;renderCtrl();renderPanel();loadTasks();
      }).catch(function(e){say(e.message,true)});
    }
    loadAll();
    return;
  }

  /* ================= 家长端：老师任务同步 + 三科学情 + 点赞鼓励 ================= */
  function loadParent(){
    api('/parent/arena-summary?subject='+encodeURIComponent(subject)).then(function(d){
      body.textContent='';
      body.appendChild(el('div',{class:'ma-card'},
        el('div',{class:'ma-eyebrow',text:'家校同步 · 小学'+subject}),
        el('h2',{class:'ma-h1',text:'孩子'+subject+'任务进度与闯关学情'}),
        el('p',{class:'ma-sub',text:'实时同步老师布置的地图/专项任务、点亮进度与待修补薄弱点，每天可给孩子点个赞送上鼓励！'})));
      body.appendChild(helperBar('这里自动汇总老师最新布置的练习任务与孩子掌握情况。点「给孩子点赞鼓励」，孩子打开自主练习时我会立刻转达你的鼓励！','长缨助手 · 家校联动'));
      if(!d.items||!d.items.length){
        body.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:'暂未关联孩子账号。'})));
        return;
      }
      d.items.forEach(function(ch){
        var st=(ch.subjects&&ch.subjects[0])||{litNodes:0,totalNodes:16,masteredNodes:0,repairNames:[],bestTier:null};
        var pct=st.totalNodes?Math.round(st.litNodes/st.totalNodes*100):0;
        var cheerBtn=el('button',{type:'button',class:'ma-btn '+(ch.cheeredToday?'ma-btn-ghost':'ma-btn-primary')+' ma-btn-sm',text:ch.cheeredToday?'👍 今日已点赞鼓励':'👍 给孩子点赞鼓励'});
        cheerBtn.disabled=!!ch.cheeredToday;
        cheerBtn.onclick=function(){
          api('/parent/arena-cheers',{method:'POST',json:{student_id:ch.studentId,subject:subject,message:'坚持'+subject+'自主练习真棒，继续加油！'}}).then(function(){
            say('已发送鼓励！孩子下次打开自主练习时，长缨助手会立刻转达！');
            loadParent();
          }).catch(function(e){say(e.message,true)});
        };
        var card=el('div',{class:'ma-card'},
          el('div',{class:'ma-sum-top'},
            el('div',{},
              el('h3',{style:'margin:0',text:ch.name+(ch.grade?'（'+ch.grade+'年级）':'')}),
              el('p',{class:'ma-sub',style:'margin-top:3px',text:'已点亮 '+st.litNodes+'/'+st.totalNodes+'（'+pct+'%）· 精通 '+st.masteredNodes+' · 专项最高：'+(st.bestTier?(st.bestTier.code+' '+st.bestTier.name):'尚未参加')})),
            el('div',{class:'ma-row'},el('span',{class:'ma-pts',text:'全站积分 '+ch.pointsBalance}),cheerBtn)),
          el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})));
        if(st.repairNames&&st.repairNames.length){
          card.appendChild(el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待修补考点：'+st.repairNames.join('、')}));
        }
        var tBox=el('div',{style:'margin-top:12px;padding-top:10px;border-top:1px solid #f1e8df'},
          el('b',{style:'font-size:13.5px',text:'老师布置的'+subject+'任务'}));
        if(!ch.tasks||!ch.tasks.length){
          tBox.appendChild(el('p',{class:'ma-sub',style:'margin-top:4px',text:'当前没有进行中的老师布置任务。'}));
        }else{
          ch.tasks.forEach(function(tk){
            var done=(tk.status==='done');
            tBox.appendChild(el('div',{class:'ma-loss-row'},
              el('span',{text:tk.targetTitle+'（'+tk.goalLabel+' · 截止 '+tk.dueDate+'）'}),
              el('span',{class:'ma-tag '+(done?'lit':'repair'),text:done?'✓ 已达标':'待完成'})));
          });
        }
        card.appendChild(tBox);
        body.appendChild(card);
      });
    }).catch(function(e){say(e.message,true)});
  }
  loadParent();
}
"""

__all__ = ["ARENA_ROLE_HUB_JS"]
