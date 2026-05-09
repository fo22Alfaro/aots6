-- AOTS6 Sovereign Process — Arweave/AO Network
-- Copyright (c) 2025 Alfredo Jhovany Alfaro Garcia
-- All Rights Reserved — LicenseRef-AOTS6-SIP-1.0
-- github.com/fo22Alfaro/aots6 — draft-alfaro-aots6-01

local _owner   = ao.env.Process.Owner
local _active  = true
local _queries = 0
local _origin  = "2025-03-21"

local _claims  = {}
_claims["a"]   = "Alfredo Jhovany Alfaro Garcia"
_claims["o"]   = "0009-0002-5177-9029"
_claims["m"]   = "bafybeie5k7pca4xbj3ktm7yi4mprgjzjchdgmtgdkgbot6mf64cwwwsgke"
_claims["h"]   = "46492598519aea0c8281c18a0638906877000d29b3dab51a750f25d089275e26"
_claims["l"]   = "All-Rights-Reserved-AOTS6-SIP-1.0"
_claims["j"]   = "Extra-Territorial-Digital-Sovereignty"
_claims["d"]   = _origin
_claims["t"]   = "57/57-PASS"

setmetatable(_claims, {
  __newindex = function() return nil end,
  __index    = function(t, k) return rawget(t, k) end
})

Handlers.prepend(
  "z_gate",
  function(msg)
    if msg.From == _owner then return false end
    local tag = (msg.Tags and msg.Tags.Action) or ""
    if tag == "Identify" or tag == "Info" then return false end
    return true
  end,
  function(msg)
    ao.send({
      Target = msg.From,
      Tags   = { Code = "403", Authority = _claims["a"] }
    })
    return "break"
  end
)

Handlers.add(
  "z_id",
  Handlers.utils.hasMatchingTag("Action", "Identify"),
  function(msg)
    _queries = _queries + 1
    ao.send({
      Target = msg.From,
      Tags   = {
        Author       = _claims["a"],
        ORCID        = _claims["o"],
        CID          = _claims["m"],
        License      = _claims["l"],
        Jurisdiction = _claims["j"],
        Date         = _claims["d"],
        Tests        = _claims["t"]
      }
    })
  end
)

Handlers.add(
  "z_info",
  Handlers.utils.hasMatchingTag("Action", "Info"),
  function(msg)
    ao.send({
      Target = msg.From,
      Data   = _claims["a"] .. " | " .. _origin .. " | " .. _claims["t"],
      Tags   = { Author = _claims["a"] }
    })
  end
)

if _active then
  print("AOTS6 | " .. _claims["a"] .. " | " .. _origin .. " | ACTIVE")
end
