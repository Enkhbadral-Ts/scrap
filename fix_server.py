import sys, re

with open('/root/khuuli-bot/server.js', 'r', encoding='utf-8') as f:
    content = f.read()

# The function sendTelegramNotification looks like this right now:
# async function sendTelegramNotification(message) {
# ...
#   } catch (e) {
#     console.error('❌ [Telegram] Failed to send:', e.message);
#   }
# 
# // --- VISIT LOGGER ---
# function logVisit(req, pageName) {
# ...
# }
# // -------------------
# } <-- missing this last brace for sendTelegramNotification

# Let's completely remove the // --- VISIT LOGGER --- block and re-insert it globally.

start_tag = "// --- VISIT LOGGER ---"
end_tag = "// -------------------"
if start_tag in content and end_tag in content:
    start_idx = content.find(start_tag)
    end_idx = content.find(end_tag) + len(end_tag)
    
    # Extract the block
    visit_logger_block = content[start_idx:end_idx]
    
    # Remove it from its current location
    content = content[:start_idx] + content[end_idx:]
    
    # The previous code might have eaten the closing brace of sendTelegramNotification.
    # Let's ensure sendTelegramNotification is properly closed.
    # Let's just find the catch block and add a closing brace if it's missing.
    catch_block = "console.error('❌ [Telegram] Failed to send:', e.message);\n  }"
    if catch_block in content:
        content = content.replace(catch_block, catch_block + "\n}\n")
    
    # Now put visit_logger_block at the end of the file, or right after the function
    content = content.replace(catch_block + "\n}\n", catch_block + "\n}\n\n" + visit_logger_block + "\n")

    with open('/root/khuuli-bot/server.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Fixed server.js scopes")
else:
    print("Tags not found.")

