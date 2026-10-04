--[[
	Plugin DinoMaker — instala os DinoKits nos dinos importados (modo edição).

	Fluxo:
	  1. Importar 3D: selecione TODOS os .fbx do lote de uma vez.
	  2. Insira o arquivo <lote>_DinoKits.rbxm (pasta "DinoKits") no Workspace.
	  3. Clique em "Instalar kits": cada kit acha o dino de melhor encaixe, entra nele e
	     monta HumanoidRootPart, Humanoid, soldas e VFX. Pronto para salvar/copiar.
	  "Passear" liga/desliga o atributo Wander de todos os dinos (teste rápido).
]]

local ChangeHistoryService = game:GetService("ChangeHistoryService")
local Selection = game:GetService("Selection")

local toolbar = plugin:CreateToolbar("DinoMaker")
local installBtn = toolbar:CreateButton("Instalar kits", "Encaixa todos os DinoKits soltos nos dinos importados", "rbxasset://textures/ui/GuiImagePlaceholder.png")
local wanderBtn = toolbar:CreateButton("Passear", "Liga/desliga Wander em todos os dinos", "rbxasset://textures/ui/GuiImagePlaceholder.png")
installBtn.ClickableWhenViewportHidden = true

local function looseKits()
	local out = {}
	for _, d in ipairs(workspace:GetDescendants()) do
		if d:IsA("Folder") and d.Name == "DinoKit" and d:FindFirstChild("DinoRig") then
			local p = d.Parent
			if not (p and p:IsA("Model") and p:GetAttribute("DinoReady")) then
				table.insert(out, d)
			end
		end
	end
	return out
end

local function installAll()
	local kits = looseKits()
	if #kits == 0 then
		warn("[DinoMaker] Nenhum DinoKit solto no Workspace. Insira o arquivo *_DinoKits.rbxm primeiro.")
		return
	end
	local recording = ChangeHistoryService:TryBeginRecording("DinoMaker: instalar kits")
	local ok, fail, models = 0, 0, {}
	for _, kit in ipairs(kits) do
		local rigModule = kit:FindFirstChild("DinoRig")
		local success, err = pcall(function()
			local Rig = require(rigModule)
			local model = Rig.findTarget(kit)
			if not model then
				error("dino não encontrado para " .. tostring(kit:GetAttribute("DinoName")))
			end
			if not Rig.setup(model, kit) then
				error("setup falhou em " .. model.Name)
			end
			table.insert(models, model)
		end)
		if success then
			ok = ok + 1
		else
			fail = fail + 1
			warn("[DinoMaker] " .. tostring(err))
		end
	end
	for _, f in ipairs(workspace:GetDescendants()) do
		if f:IsA("Folder") and f.Name == "DinoKits" and #f:GetChildren() == 0 then
			f:Destroy()
		end
	end
	if recording then
		ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
	end
	Selection:Set(models)
	print(string.format("[DinoMaker] %d dino(s) prontos, %d falha(s).", ok, fail))
end

local function toggleWander()
	local any, value = false, nil
	for _, d in ipairs(workspace:GetDescendants()) do
		if d:IsA("Model") and d:GetAttribute("DinoName") ~= nil then
			if value == nil then
				value = not d:GetAttribute("Wander")
			end
			d:SetAttribute("Wander", value)
			any = true
		end
	end
	print(any and ("[DinoMaker] Wander = " .. tostring(value)) or "[DinoMaker] Nenhum dino encontrado.")
end

installBtn.Click:Connect(installAll)
wanderBtn.Click:Connect(toggleWander)
