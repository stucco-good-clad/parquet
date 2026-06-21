/**
 * filemanager/api.js
 *
 * File manager API layer.
 * All fetch helpers for file manager operations live here.
 * Functions are global (no module system) to stay compatible with the
 * existing plain-browser-script loading approach.
 *
 * Depends on globals: appdata, getAccountActive, generateWT
 */

async function getContent(contentId, contentFilter = "", page = 1, pageSize = 1000, sortField = "createTime", sortDirection = -1) {
    try {
        const accountActive = await getAccountActive();
        const url = new URL(`https://${appdata.apiServer}.gofile.io/contents/${contentId}`);
        const params = new URLSearchParams({ contentFilter, page, pageSize, sortField, sortDirection});

        const password = sessionStorage.getItem(`password|${contentId}`);
        if (password) params.append('password', password);

        url.search = params.toString();

        const response = await fetch(url, {
            headers: { 
                'Authorization': `Bearer ${accountActive.token}`,
                'X-Website-Token': generateWT(accountActive.token),
                'X-BL': navigator.language || ''
            }
        });

        if (!response.ok) throw new Error(response.status);

        const fetchResult = await response.json();
        if (fetchResult.status !== "ok" && fetchResult.status !== "error-notFound") {
            throw new Error(fetchResult.status);
        }

        if(fetchResult.data.password && fetchResult.data.passwordStatus == "passwordWrong") {
            sessionStorage.removeItem(`password|${contentId}`);
        }

        return fetchResult;
    } catch (error) {
        throw new Error("getContent " + error.message);
    }
}

async function deleteContentsFetch(contentsId, proof) {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch('https://'+appdata.apiServer+'.gofile.io/contents', {
            method: 'DELETE',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                contentsId: contentsId,
                proof: proof,
            })
        });
        if (!response.ok) {
            throw new Error(response.status);
        }
        const result = await response.json();

        if (result.status === 'ok') {
            return result
        } else {
            throw new Error(result.status);
        }
    } catch (error) {
        throw new Error("deleteContent "+error.message);
    }
}

async function createFolderFetch(parentFolderId, folderName, isPublic) {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch('https://'+appdata.apiServer+'.gofile.io/contents/createfolder', {
            method: 'POST',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                parentFolderId: parentFolderId,
                folderName: folderName,
                public: isPublic
            })
        });
        if (!response.ok) {
            throw new Error(response.status);
        }
        const result = await response.json();

        if (result.status === 'ok') {
            return result
        } else {
            throw new Error(result);
        }
    } catch (error) {
        throw new Error("createFolder "+error.message);
    }
}

async function searchFetch(contentId, searchedString, createTimeFrom, createTimeTo) {
    try {
        const accountActive = await getAccountActive();
        const url = new URL(`https://${appdata.apiServer}.gofile.io/contents/search`);
        url.searchParams.set('contentId', contentId);
        url.searchParams.set('searchedString', searchedString);

        if (createTimeFrom !== undefined && createTimeFrom !== null && createTimeFrom !== '') {
            url.searchParams.set('createTimeFrom', createTimeFrom);
        }
        if (createTimeTo !== undefined && createTimeTo !== null && createTimeTo !== '') {
            url.searchParams.set('createTimeTo', createTimeTo);
        }

        const response = await fetch(url.toString(), {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${accountActive.token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(response.status);
        }

        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result);
        }
    } catch (error) {
        throw new Error("searchFetch " + error.message);
    }
}

async function renameContentFetch(contentId, contentName) {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/${contentId}/update`, {
            method: 'PUT',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                attribute: "name",
                attributeValue: contentName
            })
        });
        if (!response.ok) {
            throw new Error(response.status);
        }
        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result);
        }
    } catch (error) {
        throw new Error("renameContent " + error.message);
    }
}

async function copyContentFetch(contentsId, folderDestId) {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/copy`, {
            method: 'POST',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                contentsId: contentsId,
                folderId: folderDestId
            })
        });
        
        if (!response.ok) {
            throw new Error(response.status);
        }
        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result);
        }
    } catch (error) {
        throw new Error("copyContent " + error.message);
    }
}

async function moveContentFetch(contentsId, folderDestId) {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/move`, {
            method: 'PUT',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                contentsId: contentsId,
                folderId: folderDestId
            })
        });
        
        if (!response.ok) {
            throw new Error(response.status);
        }
        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result);
        }
    } catch (error) {
        throw new Error("moveContent " + error.message);
    }
}

async function importContentFetch(contentsId) {
    try {
        const accountActive = await getAccountActive();
        
        const requestBody = {
            contentsId: contentsId
        };

        const passwordKey = `password|${appdata.fileManager.mainContent.data.id}`;
        const storedPassword = sessionStorage.getItem(passwordKey);
        
        if (storedPassword) {
            requestBody.password = storedPassword;
        }

        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/import`, {
            method: 'POST',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error(response.status);
        }
        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result);
        }
    } catch (error) {
        throw new Error("importContent " + error.message);
    }
}

/**
 * Bulk-restore one or more content items from the recycle bin.
 * Backend endpoint: PUT /contents/restore
 * @param {string} contentsId - comma-separated content IDs
 * @returns {Promise<object>} API result
 */
async function restoreContentsFetch(contentsId) {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/restore`, {
            method: 'PUT',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ contentsId: contentsId })
        });

        if (!response.ok) {
            throw new Error(response.status);
        }

        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result.status);
        }
    } catch (error) {
        throw new Error("restoreContent " + error.message);
    }
}

/**
 * Permanently empty the recycle bin.
 * Backend endpoint: DELETE /contents/recycle
 * @returns {Promise<object>} API result
 */
async function emptyRecycleBinFetch() {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/recycle`, {
            method: 'DELETE',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(response.status);
        }

        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result.status);
        }
    } catch (error) {
        throw new Error("emptyRecycleBin " + error.message);
    }
}

/**
 * Disable (remove) the recycle bin for the active account.
 * Backend endpoint: DELETE /contents/removerecycle
 *
 * Possible error statuses to handle on the frontend:
 *   - error-recycleHasRecentItems  (with data.recentCount) — items < 24h old
 *   - error-recycleNotEmpty       (with data.remainingCount) — unexpected
 * @returns {Promise<object>} API result
 */
async function removeRecycleBinFetch() {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/removerecycle`, {
            method: 'DELETE',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`
            }
        });

        if (!response.ok) {
            throw new Error(response.status);
        }

        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            // Attach the full API result so callers can branch on payload status/data
            // (e.g. error-recycleHasRecentItems carries data.recentCount).
            const err = new Error(result.status);
            err.result = result;
            throw err;
        }
    } catch (error) {
        // Preserve `result` attachment across the wrapping Error, if present.
        const wrapped = new Error("removeRecycleBin " + error.message);
        if (error.result) wrapped.result = error.result;
        throw wrapped;
    }
}

/**
 * Set up (activate) the recycle bin for the active account.
 * Backend endpoint: POST /contents/setuprecycle
 * @returns {Promise<object>} API result
 */
async function setupRecycleFetch() {
    try {
        const accountActive = await getAccountActive();
        const response = await fetch(`https://${appdata.apiServer}.gofile.io/contents/setuprecycle`, {
            method: 'POST',
            headers: {
                "Authorization": `Bearer ${accountActive.token}`,
                "Content-Type": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(response.status);
        }

        const result = await response.json();

        if (result.status === 'ok') {
            return result;
        } else {
            throw new Error(result.status);
        }
    } catch (error) {
        throw new Error("setupRecycle " + error.message);
    }
}
