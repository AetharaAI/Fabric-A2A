                                                        ➜  a2a-mcp git:(main) ✗ curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST https://fabric.perceptor.us/mcp/call \
  -d '{
    "name":"fabric.tool.math.calculate",
    "arguments":{"expression":"sqrt(144) * 2"}
  }'  
      
{"ok":true,"result":{"result":24.0,"expression":"sqrt(144) * 2","type":"float"},"error":null,"trace":{"trace_id":"22848bd7-7168-4c60-8ae6-7ae0dde378ff","span_id":"d0b29013-f2c6-40b4-9208-5da053b62412","parent_span_id":null}}%                                                                       ➜  a2a-mcp git:(main) ✗ curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST https://fabric.perceptor.us/mcp/call \
  -d '{
    "name":"fabric.call",
    "arguments":{
      "agent_id":"percy",
      "capability":"reason",
      "task":"Explain recursion simply"
    }
  }'

Internal Server Error%                                                    ➜  a2a-mcp git:(m➜  a2a-mcp git:(main) ✗ curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST https://fabric.perceptor.us/mcp/call \
  -d '{
    "name":"fabric.call",
    "arguments":{
      "agent_id":"percy",
      "capability":"reason",
      "task":"Explain recursion simply"
    }
  }'

{"ok":true,"trace":{"trace_id":"24e0d057-78aa-4a76-9ec8-dd7c4e4d1caf","span_id":"b0b8802a-0dbe-4a9e-be11-bf5d968fb065","parent_span_id":null},"result":{"answer":"Mock response from percy","data":{},"artifacts":[],"citations":[]}}% 
➜  a2a-mcp git:(main) curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST https://fabric.perceptor.us/mcp/call \
  -d '{"name":"fabric.tool.list","arguments":{}}'

{"tools":[{"tool_id":"io.read_file","provider":"builtin","category":"io","available":true},{"tool_id":"io.write_file","provider":"builtin","category":"io","available":true},{"tool_id":"io.list_directory","provider":"builtin","category":"io","available":true},{"tool_id":"io.search_files","provider":"builtin","category":"io","available":true},{"tool_id":"web.http_request","provider":"builtin","category":"web","available":true},{"tool_id":"web.fetch_page","provider":"builtin","category":"web","available":true},{"tool_id":"web.parse_url","provider":"builtin","category":"web","available":true},{"tool_id":"math.calculate","provider":"builtin","category":"math","available":true},{"tool_id":"math.statistics","provider":"builtin","category":"math","available":true},{"tool_id":"text.regex","provider":"builtin","category":"text","available":true},{"tool_id":"text.transform","provider":"builtin","category":"text","available":true},{"tool_id":"text.diff","provider":"builtin","category":"text","available":true},{"tool_id":"system.execute","provider":"builtin","category":"system","available":true},{"tool_id":"system.env","provider":"builtin","category":"system","available":true},{"tool_id":"system.datetime","provider":"builtin","category":"system","available":true},{"tool_id":"data.json","provider":"builtin","category":"data","available":true},{"tool_id":"data.csv","provider":"builtin","category":"data","available":true},{"tool_id":"data.validate","provider":"builtin","category":"data","available":true},{"tool_id":"security.hash","provider":"builtin","category":"security","available":true},{"tool_id":"security.base64","provider":"builtin","category":"security","available":true},{"tool_id":"encode.url","provider":"builtin","category":"encode","available":true},{"tool_id":"docs.markdown","provider":"builtin","category":"docs","available":true},{"tool_id":"agent.percy.reason","provider":"agent","category":"agent:percy","agent_id":"percy","capability":"reason","streaming":true},{"tool_id":"agent.percy.plan","provider":"agent","category":"agent:percy","agent_id":"percy","capability":"plan","streaming":true},{"tool_id":"agent.coder.code","provider":"agent","category":"agent:coder","agent_id":"coder","capability":"code","streaming":true},{"tool_id":"agent.coder.review","provider":"agent","category":"agent:coder","agent_id":"coder","capability":"review","streaming":false},{"tool_id":"agent.vision.analyze_image","provider":"agent","category":"agent:vision","agent_id":"vision","capability":"analyze_image","streaming":false},{"tool_id":"agent.vision.generate_image","provider":"agent","category":"agent:vision","agent_id":"vision","capability":"generate_image","streaming":false},{"tool_id":"agent.memory.store","provider":"agent","category":"agent:memory","agent_id":"memory","capability":"store","streaming":false},{"tool_id":"agent.memory.recall","provider":"agent","category":"agent:memory","agent_id":"memory","capability":"recall","streaming":false},{"tool_id":"agent.orchestrator.coordinate","provider":"agent","category":"agent:orchestrator","agent_id":"orchestrator","capability":"c➜  a2a-mcp git:(main)