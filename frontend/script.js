const API_URL = "http://127.0.0.1:5000";
let sources = [];
let editingUrl = null;

// Toast notification
function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    const toastMessage = document.getElementById("toast-message");
    
    toastMessage.textContent = message;
    toast.classList.toggle("error", isError);
    toast.classList.add("show");
    
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

// Mettre à jour les statistiques
function updateStats() {
    const total = sources.length;
    const active = sources.filter(s => s.enabled).length;
    const running = sources.filter(s => s.running).length;
    
    document.getElementById("total-sources").textContent = total;
    document.getElementById("active-sources").textContent = active;
    document.getElementById("running-sources").textContent = running;
}

// Afficher les tags de mots-clés
function updateKeywordTags() {
    const input = document.getElementById("keywords");
    const tagsContainer = document.getElementById("keywords-tags");
    
    const keywords = input.value.split(",").filter(k => k.trim() !== "");
    
    tagsContainer.innerHTML = "";
    keywords.forEach((keyword, index) => {
        const tag = document.createElement("div");
        tag.className = "keyword-tag";
        tag.innerHTML = `
            ${keyword.trim()}
            <i class="fas fa-times" onclick="removeKeyword(${index})"></i>
        `;
        tagsContainer.appendChild(tag);
    });
}

// Supprimer un mot-clé
function removeKeyword(index) {
    const input = document.getElementById("keywords");
    const keywords = input.value.split(",").filter(k => k.trim() !== "");
    keywords.splice(index, 1);
    input.value = keywords.join(",");
    updateKeywordTags();
}

// Écouter les changements sur le champ keywords
document.addEventListener("DOMContentLoaded", () => {
    const keywordsInput = document.getElementById("keywords");
    keywordsInput.addEventListener("input", updateKeywordTags);
    keywordsInput.addEventListener("blur", updateKeywordTags);
});

// Ajouter une source
async function addSource() {
    const url = document.getElementById("url").value;
    const type = document.getElementById("type").value;
    const frequency = parseInt(document.getElementById("frequency").value);
    const unit = document.getElementById("unit").value;
    const maxHits = parseInt(document.getElementById("max_hits").value);
    const keywords = document.getElementById("keywords").value
        .split(",")
        .map(k => k.trim())
        .filter(k => k !== "");

    if (!url || !type || !frequency || !maxHits) {
        showToast("Veuillez remplir tous les champs", true);
        return;
    }

    const source = {
        url,
        type,
        schedule: { value: frequency, unit },
        max_hits: maxHits,
        keywords
    };

    try {
        const response = await fetch(`${API_URL}/sources`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(source)
        });

        if (response.ok) {
            showToast("✓ Source ajoutée avec succès");
            await loadSources();
            clearForm();
        } else {
            const error = await response.json();
            showToast(`Erreur: ${error.message || "Échec de l'ajout"}`, true);
        }
    } catch (error) {
        showToast("Erreur de connexion au serveur", true);
        console.error(error);
    }
}

// Charger les sources
async function loadSources() {
    const loading = document.getElementById("loading");
    const emptyState = document.getElementById("empty-state");
    const list = document.getElementById("sources-list");

    loading.style.display = "block";
    list.style.display = "none";
    emptyState.style.display = "none";

    try {
        const response = await fetch(`${API_URL}/sources`);
        sources = await response.json();

        loading.style.display = "none";

        if (sources.length === 0) {
            emptyState.style.display = "block";
        } else {
            list.style.display = "block";
            renderSources(sources);
        }

        updateStats();
    } catch (error) {
        loading.style.display = "none";
        showToast("Erreur lors du chargement des sources", true);
        console.error(error);
    }
}

// Afficher les sources
function renderSources(sourcesToRender) {
    const list = document.getElementById("sources-list");
    list.innerHTML = "";

    sourcesToRender.forEach(source => {
        const li = document.createElement("li");
        li.className = "source-card";
        
        const statusClass = source.running ? "running" : (source.enabled ? "enabled" : "disabled");
        const statusText = source.running ? "En cours" : (source.enabled ? "Activée" : "Désactivée");
        const statusIcon = source.running ? "fa-spinner fa-spin" : (source.enabled ? "fa-check-circle" : "fa-times-circle");

        li.innerHTML = `
            <div class="source-header">
                <div class="source-url">
                    <i class="fas fa-link"></i>
                    ${source.url}
                </div>
                <span class="source-type">${source.type}</span>
            </div>
            
            <div class="source-status ${statusClass}">
                <i class="fas ${statusIcon}"></i>
                ${statusText}
            </div>
            
            <div class="source-info">
                <div class="info-item">
                    <i class="fas fa-clock"></i>
                    <span>Toutes les ${source.schedule.value} ${source.schedule.unit}</span>
                </div>
                <div class="info-item">
                    <i class="fas fa-hashtag"></i>
                    <span>Max: ${source.max_hits} hits</span>
                </div>
                <div class="info-item">
                    <i class="fas fa-key"></i>
                    <span>${source.keywords.length} mots-clés</span>
                </div>
            </div>
            
            ${source.keywords.length > 0 ? `
                <div class="source-keywords">
                    ${source.keywords.map(k => `<span>${k}</span>`).join("")}
                </div>
            ` : ""}
            
            <div class="source-actions">
                ${!source.running ? `
                    <button class="action-btn start" onclick="startSource('${source.url}')">
                        <i class="fas fa-play"></i> Démarrer
                    </button>
                ` : `
                    <button class="action-btn stop" onclick="stopSource('${source.url}')">
                        <i class="fas fa-stop"></i> Arrêter
                    </button>
                `}
                <button class="action-btn toggle" onclick="toggleSource('${source.url}')">
                    <i class="fas fa-toggle-${source.enabled ? 'on' : 'off'}"></i>
                    ${source.enabled ? "Désactiver" : "Activer"}
                </button>
                <button class="action-btn edit" onclick="editSource('${source.url}')">
                    <i class="fas fa-edit"></i> Modifier
                </button>
                <button class="action-btn delete" onclick="confirmDelete('${source.url}')">
                    <i class="fas fa-trash"></i> Supprimer
                </button>
            </div>
        `;

        list.appendChild(li);
    });
}

// Filtrer les sources
function filterSources() {
    const searchTerm = document.getElementById("search").value.toLowerCase();
    
    const filtered = sources.filter(source => {
        return source.url.toLowerCase().includes(searchTerm) ||
               source.type.toLowerCase().includes(searchTerm) ||
               source.keywords.some(k => k.toLowerCase().includes(searchTerm));
    });
    
    renderSources(filtered);
}

// Démarrer une source
async function startSource(url) {
    try {
        const response = await fetch(`${API_URL}/sources/${encodeURIComponent(url)}/start`, {
            method: "POST"
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast("✓ Source démarrée");
            await loadSources();
        } else {
            showToast(`Erreur: ${data.message}`, true);
        }
    } catch (error) {
        showToast("Erreur lors du démarrage", true);
        console.error(error);
    }
}

// Arrêter une source
async function stopSource(url) {
    try {
        const response = await fetch(`${API_URL}/sources/${encodeURIComponent(url)}/stop`, {
            method: "POST"
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast("✓ Source arrêtée");
            await loadSources();
        } else {
            showToast(`Erreur: ${data.message}`, true);
        }
    } catch (error) {
        showToast("Erreur lors de l'arrêt", true);
        console.error(error);
    }
}

// Activer/Désactiver une source
async function toggleSource(url) {
    try {
        const response = await fetch(`${API_URL}/sources/${encodeURIComponent(url)}/toggle`, {
            method: "PUT"
        });
        
        if (response.ok) {
            const source = sources.find(s => s.url === url);
            const newState = source ? !source.enabled : true;
            showToast(`✓ Source ${newState ? "activée" : "désactivée"}`);
            await loadSources();
        } else {
            showToast("Erreur lors du basculement", true);
        }
    } catch (error) {
        showToast("Erreur lors du basculement", true);
        console.error(error);
    }
}

// Confirmer la suppression
function confirmDelete(url) {
    if (confirm(`Êtes-vous sûr de vouloir supprimer la source "${url}" ?`)) {
        deleteSource(url);
    }
}

// Supprimer une source
async function deleteSource(url) {
    try {
        const response = await fetch(`${API_URL}/sources/${encodeURIComponent(url)}`, {
            method: "DELETE"
        });
        
        if (response.ok) {
            showToast("✓ Source supprimée");
            await loadSources();
        } else {
            showToast("Erreur lors de la suppression", true);
        }
    } catch (error) {
        showToast("Erreur lors de la suppression", true);
        console.error(error);
    }
}

// Éditer une source
function editSource(url) {
    const source = sources.find(s => s.url === url);
    
    if (source) {
        editingUrl = url;
        
        document.getElementById("url").value = source.url;
        document.getElementById("type").value = source.type;
        document.getElementById("frequency").value = source.schedule.value;
        document.getElementById("unit").value = source.schedule.unit;
        document.getElementById("max_hits").value = source.max_hits;
        document.getElementById("keywords").value = source.keywords.join(", ");
        
        updateKeywordTags();
        
        // Changer le titre et le bouton
        document.getElementById("form-title").innerHTML = '<i class="fas fa-edit"></i> Modifier la source';
        const submitBtn = document.getElementById("submit");
        submitBtn.innerHTML = '<i class="fas fa-save"></i> Enregistrer les modifications';
        submitBtn.onclick = () => updateSource(url);
        
        // Scroll vers le formulaire
        document.querySelector(".form-container").scrollIntoView({ behavior: "smooth" });
    }
}

// Mettre à jour une source
async function updateSource(originalUrl) {
    const url = document.getElementById("url").value;
    const type = document.getElementById("type").value;
    const frequency = parseInt(document.getElementById("frequency").value);
    const unit = document.getElementById("unit").value;
    const maxHits = parseInt(document.getElementById("max_hits").value);
    const keywords = document.getElementById("keywords").value
        .split(",")
        .map(k => k.trim())
        .filter(k => k !== "");

    if (!url || !type || !frequency || !maxHits) {
        showToast("Veuillez remplir tous les champs", true);
        return;
    }

    const data = {
        url,
        type,
        schedule: { value: frequency, unit },
        max_hits: maxHits,
        keywords
    };

    try {
        const response = await fetch(`${API_URL}/sources/${encodeURIComponent(originalUrl)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            showToast("✓ Source mise à jour avec succès");
            await loadSources();
            clearForm();
        } else {
            const error = await response.json();
            showToast(`Erreur: ${error.message || "Échec de la mise à jour"}`, true);
        }
    } catch (error) {
        showToast("Erreur de connexion au serveur", true);
        console.error(error);
    }
}

// Réinitialiser le formulaire
function clearForm() {
    editingUrl = null;
    
    document.getElementById("url").value = "";
    document.getElementById("type").value = "";
    document.getElementById("frequency").value = "";
    document.getElementById("unit").value = "minutes";
    document.getElementById("max_hits").value = "";
    document.getElementById("keywords").value = "";
    
    updateKeywordTags();
    
    document.getElementById("form-title").innerHTML = '<i class="fas fa-plus-circle"></i> Ajouter une source';
    const submitBtn = document.getElementById("submit");
    submitBtn.innerHTML = '<i class="fas fa-plus"></i> Ajouter la source';
    submitBtn.onclick = addSource;
}

// Charger les sources au démarrage
loadSources();


async function searchInCrawledData() {
    const keyword = document.getElementById("crawl-search-input").value.trim();
    const container = document.getElementById("crawl-results");

    if (!keyword) {
        showToast("Entrez un mot-clé", true);
        return;
    }

    container.innerHTML = "🔎 Recherche en cours...";

    try {
        const response = await fetch(`${API_URL}/search?q=${encodeURIComponent(keyword)}`);
        if (!response.ok) {
            container.innerHTML = "❌ Erreur serveur.";
            return;
        }

        const results = await response.json();
        container.innerHTML = "";

        if (!Array.isArray(results) || results.length === 0) {
            container.innerHTML = "<p>Aucun résultat trouvé.</p>";
            return;
        }

        results.forEach((r, idx) => {
            const div = document.createElement("div");
            div.className = "crawl-result-card";

            const contentSnippet = (r.content || "").substring(0, 300);
            const fullContent = r.content || "";

            div.innerHTML = `
                <b>🔗 ${r.url}</b><br>
                <small>📅 ${new Date(r.crawled_at).toLocaleString()}</small><br>
                <b>Mots-clés:</b> ${(r.keywords || []).join(", ") || "Aucun"}<br>
                <p id="snippet-${idx}">${contentSnippet}...</p>
                ${fullContent.length > 300 ? `<button class="show-more-btn" onclick="toggleContent(${idx}, \`${fullContent}\`)">Voir plus</button>` : ""}
            `;

            container.appendChild(div);
        });

    } catch (err) {
        console.error(err);
        container.innerHTML = "❌ Erreur lors de la recherche.";
    }
}

function toggleContent(idx, fullText) {
    const p = document.getElementById(`snippet-${idx}`);
    const btn = p.nextElementSibling;
    if (p.textContent.endsWith("...")) {
        p.textContent = fullText;
        if(btn) btn.textContent = "Voir moins";
    } else {
        p.textContent = fullText.substring(0, 300) + "...";
        if(btn) btn.textContent = "Voir plus";
    }
}
