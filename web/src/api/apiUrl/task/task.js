import {GET, POST, reUrl} from '../../axiosconfig/axiosconfig'

export default {
    login: function(params) {
        return POST(reUrl + '/api/token/', params)
    },
    loginInfo: function(params) {
        return GET(reUrl + '/user/info/', params)
    },
    logout: function(params) {
        return POST(reUrl + '/logout/', params)
    },
    fileList: function(params) {
        return POST(reUrl + '/api/file_list/', params)
    },
    musicId3: function(params) {
        return POST(reUrl + '/api/music_id3/', params)
    },
    updateId3: function(params) {
        return POST(reUrl + '/api/update_id3/', params)
    },
    batchUpdateId3: function(params) {
        return POST(reUrl + '/api/batch_update_id3/', params)
    },
    batchAutoUpdateId3: function(params) {
        return POST(reUrl + '/api/batch_auto_update_id3/', params)
    },
    tidyFolder: function(params) {
        return POST(reUrl + '/api/tidy_folder/', params)
    },
    fetchId3Title: function(params) {
        return POST(reUrl + '/api/fetch_id3_by_title/', params)
    },
    fetchLyric: function(params) {
        return POST(reUrl + '/api/fetch_lyric/', params)
    },
    translationLyc: function(params) {
        return POST(reUrl + '/api/translation_lyc/', params)
    },
    getRecord: function(params) {
        return GET(reUrl + '/api/record/', params)
    },
    getRecordStats: function(params) {
        return GET(reUrl + '/api/record/stats/', params)
    },
    clearRecord: function(params) {
        return POST(reUrl + '/api/record/clear/', params)
    },
    retrySingleRecord: function(params) {
        return POST(reUrl + '/api/record/retry_single/', params)
    },
    resumePending: function(params) {
        return POST(reUrl + '/api/record/resume_pending/', params)
    },
    forceRefreshCache: function(params) {
        return POST(reUrl + '/api/force_refresh_cache/', params)
    },
    batchProgress: function(params) {
        return GET(reUrl + '/api/batch_progress/', params)
    },
    folderMusicList: function(params) {
        return POST(reUrl + '/api/folder_music_list/', params)
    },
    retryFailed: function(params) {
        return POST(reUrl + '/api/retry_failed/', params)
    }
}
