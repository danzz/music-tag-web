<template>
    <div class="home-main-layout">
        <!-- 顶部智能目录导航栏 -->
        <div class="top-nav-bar">
            <!-- 左侧快捷动作 -->
            <div class="top-nav-left">
                <bk-button size="small" :text="true" @click="backDir" :disabled="isAtRoot" class="nav-act-btn" title="返回上一级目录">
                    <bk-icon type="arrows-left-shape" style="font-size: 15px; margin-right: 4px;"></bk-icon> 上级
                </bk-button>
                <bk-button size="small" :text="true" @click="refreshDir" class="nav-act-btn" title="刷新当前目录">
                    <bk-icon type="refresh" style="font-size: 14px; margin-right: 4px;"></bk-icon> 刷新
                </bk-button>
                <bk-button size="small" :text="true" @click="handleForceRefreshCache" class="nav-act-btn force-refresh-btn" title="强制清空服务端与本地所有缓存，重新从磁盘深度扫描加载" :loading="isForceRefreshing">
                    <bk-icon type="refresh" style="font-size: 14px; margin-right: 4px; color: #ff9c01;"></bk-icon>
                    <span style="color: #ff9c01; font-weight: 500;">强制刷新</span>
                </bk-button>
            </div>

            <!-- 中间面包屑导航或路径直接编辑 -->
            <div class="top-nav-center">
                <div v-if="!isEditingPath" class="path-breadcrumb-wrap">
                    <div class="path-breadcrumb">
                        <span class="path-segment root-segment" @click="navigateToPath('/')" title="跳转至根目录 /">
                            <bk-icon type="folder-open" style="margin-right: 4px; color: #3a84ff;"></bk-icon>
                            <span>根目录</span>
                        </span>
                        <template v-for="(seg, idx) in pathSegments">
                            <span class="path-separator" :key="'sep-' + idx">/</span>
                            <span class="path-segment" :key="'seg-' + idx" @click="navigateToSegment(idx)" :title="'跳转至 ' + seg.path">
                                {{ seg.name }}
                            </span>
                        </template>
                    </div>
                    <span class="edit-path-btn" @click="startEditPath" title="点击手动输入/粘贴路径">
                        <bk-icon type="edit"></bk-icon>
                    </span>
                </div>
                <div v-else class="path-input-wrap">
                    <bk-input
                        ref="pathInputRef"
                        v-model="inputFilePath"
                        size="small"
                        placeholder="请输入或粘贴完整目录路径，按 Enter 回车进入"
                        @enter="confirmInputPath"
                        @keydown.esc.native="cancelEditPath">
                    </bk-input>
                    <bk-button size="small" theme="primary" @click="confirmInputPath" style="margin-left: 8px;">进入</bk-button>
                    <bk-button size="small" @click="cancelEditPath" style="margin-left: 6px;">取消</bk-button>
                </div>
            </div>

            <!-- 右侧动作：任务列表、浏览目录弹窗、历史记录下拉 -->
            <div class="top-nav-right">
                <bk-button size="small" :theme="taskStats.failed > 0 ? 'danger' : 'default'" :outline="true" @click="openTaskDrawer" title="查看批量任务执行历史与失败详情" style="margin-right: 8px;">
                    <bk-icon :type="taskStats.running > 0 || isBatchSubmitting ? 'circle-2-1' : 'order'" :class="{ 'spin-icon': taskStats.running > 0 || isBatchSubmitting }" style="margin-right: 4px;"></bk-icon>
                    任务列表
                    <span v-if="taskStats.failed > 0" class="task-badge-pill pill-failed">{{ taskStats.failed }} 失败</span>
                    <span v-else-if="taskStats.total > 0" class="task-badge-pill pill-total">{{ taskStats.total }}</span>
                </bk-button>

                <bk-button size="small" theme="primary" :outline="true" @click="openDirBrowser" class="browse-dir-btn" style="margin-right: 8px;">
                    <bk-icon type="folder" style="margin-right: 4px;"></bk-icon> 浏览目录
                </bk-button>

                <bk-dropdown-menu align="right" class="history-dropdown">
                    <template slot="dropdown-trigger">
                        <bk-button size="small" :outline="true" title="查看最近访问的目录">
                            <bk-icon type="time" style="margin-right: 4px;"></bk-icon> 历史 ({{ recentDirs.length }})
                            <bk-icon type="angle-down" style="margin-left: 4px;"></bk-icon>
                        </bk-button>
                    </template>
                    <ul class="bk-dropdown-list history-dropdown-list" slot="dropdown-content">
                        <li v-if="recentDirs.length === 0" class="history-empty" style="padding: 8px 12px; color: #979ba5; font-size: 12px;">暂无历史记录</li>
                        <li v-for="(dir, dIdx) in recentDirs" :key="dIdx" @click="selectRecentDir(dir)" :title="dir" class="history-item">
                            <a href="javascript:;"><bk-icon type="folder" style="margin-right: 6px; color: #63656e;"></bk-icon>{{ dir }}</a>
                        </li>
                        <li v-if="recentDirs.length > 0" class="clear-history-item" @click.stop="clearRecentDirs">
                            <a href="javascript:;" style="color: #ea3636; font-size: 12px; text-align: center; border-top: 1px solid #dcdee5;">清空历史</a>
                        </li>
                    </ul>
                </bk-dropdown-menu>
            </div>
        </div>

        <!-- 主工作区：左侧全宽展示表格，右侧为抽屉式单曲编辑面板 -->
        <div class="main-workspace">
            <div class="resource-section" :class="{ 'with-drawer-open': Boolean(musicInfo.title) }">
            <!-- 顶部控制工具栏 -->
            <div class="resource-header">
                <div v-if="activeRightTab === 'fileList'" class="file-list-toolbar">
                    <div style="display: flex; align-items: center;">
                        <span class="size-btn size-small" :class="{ 'active-size': tableSize === 'small' }" @click="setTableSize('small')" title="紧凑字号">Tt</span>
                        <span class="size-btn size-medium" :class="{ 'active-size': tableSize === 'medium' }" @click="setTableSize('medium')" title="标准字号">Tt</span>
                        <span class="size-btn size-large" :class="{ 'active-size': tableSize === 'large' }" @click="setTableSize('large')" title="大字号">Tt</span>
                        <span class="toolbar-label">每页:</span>
                        <select v-model="tablePageSize" @change="handlePageSizeChange" class="page-size-select">
                            <option :value="32">32</option>
                            <option :value="64">64</option>
                            <option :value="128">128</option>
                            <option :value="256">256</option>
                            <option :value="512">512</option>
                            <option :value="1000">1000</option>
                        </select>
                        <bk-button size="small" theme="primary" :outline="true" @click="openMultiBatchModal('title')" style="margin-left: 12px; height: 26px; line-height: 24px; padding: 0 10px;">
                            <bk-icon type="edit" style="margin-right: 4px;"></bk-icon>批量修改
                        </bk-button>

                        <bk-button size="small" theme="warning" @click="openAiPlanDialog" style="margin-left: 8px; height: 26px; line-height: 24px; padding: 0 10px; font-weight: bold; background: linear-gradient(135deg, #ff9c00, #ff6a00); border-color: #ff6a00; color: #fff;">
                            <bk-icon type="data-shape" style="margin-right: 4px;"></bk-icon>⚡ 智能规划
                        </bk-button>

                        <bk-button size="small" theme="success" @click="openCourseCoverDialog" style="margin-left: 8px; height: 26px; line-height: 24px; padding: 0 10px; font-weight: bold; background: linear-gradient(135deg, #10b981, #059669); border-color: #059669; color: #fff;">
                            <bk-icon type="image" style="margin-right: 4px;"></bk-icon>🎨 课程封面
                        </bk-button>

                        <bk-dropdown-menu align="left" style="margin-left: 8px;">
                            <template slot="dropdown-trigger">
                                <bk-button size="small" :outline="true" style="height: 26px; line-height: 24px; padding: 0 8px;">更多操作 <bk-icon type="angle-down"></bk-icon></bk-button>
                            </template>
                            <ul class="bk-dropdown-list" slot="dropdown-content">
                                <li><a href="javascript:;" @click="openCourseCoverDialog"><bk-icon type="image" style="margin-right: 6px; color: #10b981;"></bk-icon>🎨 课程封面制作与生成</a></li>
                                <li><a href="javascript:;" @click="openAiPlanDialog"><bk-icon type="data-shape" style="margin-right: 6px; color: #ff9c00;"></bk-icon>⚡ 智能规划</a></li>
                                <li><a href="javascript:;" @click="openPromptManager"><bk-icon type="cog" style="margin-right: 6px;"></bk-icon>提示词模板管理</a></li>
                                <li><a href="javascript:;" @click="openAiSettings"><bk-icon type="key" style="margin-right: 6px;"></bk-icon>模型与 API 设置</a></li>
                                <li><a href="javascript:;" @click="exampleSetting1.primary.visible = true"><bk-icon type="magic" style="margin-right: 6px;"></bk-icon>自动匹配修改</a></li>
                                <li><a href="javascript:;" @click="openTidyModal"><bk-icon type="folder-open" style="margin-right: 6px;"></bk-icon>整理分类文件夹</a></li>
                            </ul>
                        </bk-dropdown-menu>

                        <span class="selected-count-badge" v-if="tableSelectedRows.length > 0" style="margin-left: 8px; font-size: 12px; color: #3a84ff; background: #e1ecff; padding: 2px 8px; border-radius: 10px; display: inline-flex; align-items: center;">
                            已选 {{ tableSelectedRows.length }} 首
                            <i class="bk-icon icon-close" @click="clearTableSelection" style="cursor: pointer; margin-left: 6px; font-size: 10px;" title="清空已选"></i>
                        </span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <bk-input
                            type="text"
                            size="small"
                            v-model="searchWord"
                            placeholder="根据文件名搜索"
                            @enter="handleSearchSubmit"
                            :clearable="true"
                            @clear="handleSearchSubmit"
                            style="width: 200px; margin-right: 8px;">
                        </bk-input>
                        <bk-dropdown-menu :align="'right'" style="margin-right: 12px;">
                            <template slot="dropdown-trigger">
                                <bk-button size="small" :outline="true" title="文件排序">
                                    <span class="bk-icon icon-sort" style="margin-right: 4px;"></span>
                                    {{ currentSortLabel }}
                                </bk-button>
                            </template>
                            <ul class="bk-dropdown-list" slot="dropdown-content">
                                <li><a href="javascript:;" @click="changeSorted('name')" :class="{ 'isSelected': sortedField.includes('name') }">按文件名</a></li>
                                <li><a href="javascript:;" @click="changeSorted('update_time')" :class="{ 'isSelected': sortedField.includes('update_time') }">按修改时间</a></li>
                                <li><a href="javascript:;" @click="changeSorted('size')" :class="{ 'isSelected': sortedField.includes('size') }">按文件大小</a></li>
                            </ul>
                        </bk-dropdown-menu>
                        <span class="total-count-text">数量: {{ folderMusicTotal }}</span>
                    </div>
                </div>
                <div v-else class="subview-toolbar">
                    <bk-button :text="true" theme="primary" @click="activeRightTab = 'fileList'" style="font-size: 13px;">
                        <bk-icon type="arrows-left-shape" style="margin-right: 5px;"></bk-icon> 返回文件列表
                    </bk-button>
                    <span style="font-size: 13px; font-weight: 500; color: #495060;">
                        {{ activeRightTab === 'searchList' ? '在线刮削候选' : '歌词翻译' }}
                    </span>
                    <span style="width: 80px;"></span>
                </div>
            </div>

            <!-- 1. 文件信息列表视图 (默认视图) -->
            <div v-show="activeRightTab === 'fileList'" class="table-container" v-bkloading="{ isLoading: isTableLoading }">
                <div class="table-body-wrap">
                    <bk-table
                        ref="musicTable"
                        :data="folderMusicList"
                        :size="tableSize"
                        height="100%"
                        :row-class-name="tableRowClassName"
                        @row-click="handleTableRowClick"
                        @selection-change="handleTableSelectionChange"
                        :outer-border="false"
                        :header-border="false"
                        style="width: 100%; border: none;">
                        <bk-table-column type="selection" width="45" align="center"></bk-table-column>
                        <bk-table-column label="状态" width="105" align="center">
                            <template slot-scope="props">
                                <span v-if="getFileStatus(props.row) === 'wait'" class="batch-status-badge status-wait">
                                    <i class="bk-icon icon-clock"></i> 待修改
                                </span>
                                <span v-else-if="getFileStatus(props.row) === 'running'" class="batch-status-badge status-running">
                                    <i class="bk-icon icon-circle-2-1 spin-icon"></i> 修改中
                                </span>
                                <span v-else-if="getFileStatus(props.row) === 'success'" class="batch-status-badge status-success">
                                    <i class="bk-icon icon-check-1"></i> 已修改
                                </span>
                                <span v-else-if="getFileStatus(props.row) === 'failed'" class="batch-status-badge status-failed" v-bk-tooltips="getFileStatusExtra(props.row) || '修改失败'">
                                    <i class="bk-icon icon-close"></i> 失败
                                </span>
                                <span v-else class="batch-status-badge status-none">
                                    无修改
                                </span>
                            </template>
                        </bk-table-column>
                        <bk-table-column width="75" align="center" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'album_img', '封面')">
                            <template slot-scope="props">
                                <div class="table-cover-box" :class="'cover-' + tableSize">
                                    <img v-if="props.row.has_cover" :src="props.row.cover_url + (cacheBuster ? '&t=' + cacheBuster : '')" :key="props.row.cover_url + (cacheBuster ? '-' + cacheBuster : '')" class="table-cover-img" loading="lazy" @error="props.row.has_cover = false" />
                                    <div v-else class="table-cover-placeholder"></div>
                                </div>
                            </template>
                        </bk-table-column>
                        <bk-table-column prop="filename" min-width="160" :show-overflow-tooltip="true" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'filename', '文件名')"></bk-table-column>
                        <bk-table-column prop="title" min-width="150" :show-overflow-tooltip="true" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'title', '标题')"></bk-table-column>
                        <bk-table-column prop="artist" min-width="130" :show-overflow-tooltip="true" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'artist', '艺术家')"></bk-table-column>
                        <bk-table-column prop="album" min-width="150" :show-overflow-tooltip="true" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'album', '专辑')"></bk-table-column>
                        <bk-table-column prop="albumartist" min-width="120" :show-overflow-tooltip="true" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'albumartist', '专辑艺术家')"></bk-table-column>
                        <bk-table-column prop="tracknumber" width="85" align="center" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'tracknumber', '音轨号')">
                            <template slot-scope="props">
                                <span>{{ props.row.tracknumber && props.row.tracknumber !== '0' ? props.row.tracknumber : '' }}</span>
                            </template>
                        </bk-table-column>
                        <bk-table-column prop="discnumber" width="85" align="center" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'discnumber', '光盘号')">
                            <template slot-scope="props">
                                <span>{{ props.row.discnumber && props.row.discnumber !== '0' ? props.row.discnumber : '' }}</span>
                            </template>
                        </bk-table-column>
                        <bk-table-column label="歌词" width="70" align="center">
                            <template slot-scope="props">
                                <span class="pill-badge" :class="{ 'pill-badge-has': props.row.has_lyrics }">
                                    {{ props.row.has_lyrics ? '有' : '无' }}
                                </span>
                            </template>
                        </bk-table-column>
                        <bk-table-column label="LRC" width="70" align="center">
                            <template slot-scope="props">
                                <span class="pill-badge" :class="{ 'pill-badge-has': props.row.has_lrc }">
                                    {{ props.row.has_lrc ? '有' : '无' }}
                                </span>
                            </template>
                        </bk-table-column>
                        <bk-table-column prop="year" width="80" align="center" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'year', '年份')">
                            <template slot-scope="props">
                                <span>{{ props.row.year && props.row.year !== '0' ? props.row.year : '' }}</span>
                            </template>
                        </bk-table-column>
                        <bk-table-column prop="genre" width="85" align="center" :render-header="(h, data) => renderHeaderWithBatch(h, data, 'genre', '风格')">
                            <template slot-scope="props">
                                <span>{{ props.row.genre && props.row.genre !== '未知' ? props.row.genre : '' }}</span>
                            </template>
                        </bk-table-column>
                    </bk-table>
                </div>
                <div v-if="folderMusicTotal > 0" class="table-pagination-wrap">
                    <bk-pagination
                        :current.sync="tablePage"
                        :count="folderMusicTotal"
                        :limit="tablePageSize"
                        :limit-list="pageSizeList"
                        @change="handleTablePageChange"
                        @limit-change="handlePageLimitChange"
                        size="small"
                        align="right"
                        :show-total-count="true">
                    </bk-pagination>
                </div>
            </div>

            <!-- 2. 在线刮削搜索候选视图 -->
            <transition name="bk-slide-fade-left">
                <div
                    style="display: flex;flex-direction: column;flex: 1;margin: 15px 20px;overflow-y: auto;"
                    v-show="activeRightTab === 'searchList'">
                    <div v-if="SongList.length === 0">
                        <span style="margin-left: 30%;margin-top: 30%;">暂无匹配候选歌曲</span>
                    </div>
                    <div v-else>
                        <div class="parent">
                            <div class="title2">应用</div>
                            <div class="title2">封面</div>
                            <div class="title2">标题</div>
                            <div class="title2">艺术家</div>
                            <div class="title2">专辑</div>
                            <div class="title2">歌词</div>
                            <div class="title2">年份</div>
                        </div>
                        <div v-for="(item,index) in SongList" :key="index" style="margin-bottom: 10px;" class="parent">
                            <bk-icon type="arrows-left-shape" @click="copyAll(item)"
                                style="margin-right: 5px;cursor: pointer;"></bk-icon>
                            <div v-if="resource === 'smart_tag'">
                                <bk-badge class="mr40" :theme="'warning'" :val="item.score" radius="20%">
                                    <bk-image fit="contain" :src="item.album_img"
                                        style="width: 64px;cursor: pointer;"
                                        @click="handleCopy('album_img',item.album_img)">
                                    </bk-image>
                                </bk-badge>
                            </div>
                            <div v-else>
                                <bk-image fit="contain" :src="item.album_img"
                                    style="width: 64px;cursor: pointer;"
                                    @click="handleCopy('album_img',item.album_img)">
                                </bk-image>
                            </div>
                            <div @click="handleCopy('title',item.name)" class="music-item">
                                {{ item.name }}
                            </div>
                            <div @click="handleCopy('artist',item.artist)" class="music-item">
                                {{ item.artist }}
                            </div>
                            <div @click="handleCopy('album',item.album)" class="music-item">
                                {{ item.album }}
                            </div>
                            <div @click="handleCopy('lyric',item)" class="music-item">加载歌词</div>
                            <div @click="handleCopy('year',item.year)" class="music-item">
                                {{ item.year }}
                            </div>
                            <bk-divider></bk-divider>
                            <bk-divider></bk-divider>
                            <bk-divider></bk-divider>
                            <bk-divider></bk-divider>
                            <bk-divider></bk-divider>
                            <bk-divider></bk-divider>
                            <bk-divider></bk-divider>
                        </div>
                    </div>
                </div>
            </transition>

            <!-- 3. 歌词翻译视图 -->
            <transition name="bk-slide-fade-left">
                <div v-show="activeRightTab === 'translation'" style="flex: 1;margin: 15px 20px;overflow-y: auto;">
                    <div style="display: flex;height: 100%;">
                        <bk-icon type="arrows-left-shape" @click="handleCopy('lyric_tran',translationText)"
                            style="margin-right: 5px;margin-left: 15px;margin-top: 50%;cursor: pointer;"></bk-icon>
                        <div style="width: 100%;height: 100%;">
                            <bk-input :clearable="true" v-model="translationText" type="textarea" :rows="50"
                                style="height: 100%;">
                            </bk-input>
                        </div>
                    </div>
                </div>
            </transition>
        </div>

        <!-- 右侧单曲编辑抽屉 -->
        <transition name="drawer-slide">
            <div class="song-edit-drawer" v-show="Boolean(fileName)">
                <div class="drawer-header">
                    <div style="display: flex; align-items: center; overflow: hidden; max-width: 270px;">
                        <span style="font-weight: 600; font-size: 14px; color: #313238; white-space: nowrap;">编辑歌曲标签</span>
                        <span style="font-size: 12px; color: #979ba5; margin-left: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="fileName">({{ fileName }})</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <bk-button size="small" theme="primary" :loading="isLoading" @click="handleClick" style="margin-right: 8px;">保存信息</bk-button>
                        <div style="cursor: pointer; margin-right: 12px;" @click="exampleSetting3.primary.visible = true" title="配置">
                            <bk-icon type="cog-shape" style="font-size: 16px; color: #63656e;"></bk-icon>
                        </div>
                        <div style="cursor: pointer;" @click="closeEditSection" title="收起编辑面板">
                            <bk-icon type="close-circle-shape" style="font-size: 16px; color: #979ba5;"></bk-icon>
                        </div>
                    </div>
                </div>
                <div class="drawer-body">
<div style="display: flex;margin-bottom: 10px;align-items: center;margin-top: 10px;">
                        <div class="label1 can-copy" v-bk-tooltips="'变量名:${title}'" v-bk-copy="'${title}'">标题：</div>
                        <div style="width: 70%;">
                            <bk-input :clearable="true" v-model="musicInfo.title"></bk-input>
                        </div>
                        <div>
                            <bk-icon type="arrows-right-shape" @click="toggleLock('title')"
                                style="cursor: pointer;color: #64c864;margin-left: 20px;">
                            </bk-icon>
                        </div>
                    </div>
                    <div v-for="(item, index) in showFields" :key="'l1' + index">
                        <div class="edit-item" v-if="item === 'filename'">
                            <div class="label1 can-copy" v-bk-tooltips="'变量名:${filename}'" v-bk-copy="'${filename}'">
                                文件名：
                            </div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.filename"></bk-input>
                            </div>
                        </div>
                        <div class="edit-item can-copy" v-else-if="item === 'artist'">
                            <div class="label1" v-bk-tooltips="'变量名:${artist}'" v-bk-copy="'${artist}'">艺术家：</div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.artist"></bk-input>
                            </div>
                        </div>
                        <div class="edit-item can-copy" v-else-if="item === 'album'">
                            <div class="label1" v-bk-tooltips="'变量名:${album}'" v-bk-copy="'${album}'">专辑：</div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.album"></bk-input>
                            </div>
                        </div>
                        <div class="edit-item can-copy" v-else-if="item === 'albumartist'">
                            <div class="label1" v-bk-tooltips="'变量名:${albumartist}'" v-bk-copy="'${albumartist}'">
                                专辑艺术家：
                            </div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.albumartist"></bk-input>
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'genre'">
                            <div class="label1">风格：</div>
                            <div style="width: 70%;">
                                <bk-select
                                    :disabled="false"
                                    v-model="musicInfo.genre"
                                    style="width: 250px;background: #fff;"
                                    ext-cls="select-custom"
                                    ext-popover-cls="select-popover-custom"
                                    :placeholder="'请选择歌曲风格'"
                                    searchable>
                                    <bk-option v-for="option in genreList"
                                        :key="option.id"
                                        :id="option.id"
                                        :name="option.name">
                                    </bk-option>
                                </bk-select>
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'language'">
                            <div class="label1">语言：</div>
                            <div style="width: 70%;">
                                <bk-select
                                    :disabled="false"
                                    v-model="musicInfo.language"
                                    style="width: 250px;background: #fff;"
                                    ext-cls="select-custom"
                                    ext-popover-cls="select-popover-custom"
                                    :placeholder="'请选择歌曲语言'"
                                    searchable>
                                    <bk-option v-for="option in languageList"
                                        :key="option.id"
                                        :id="option.id"
                                        :name="option.name">
                                    </bk-option>
                                </bk-select>
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'year'">
                            <div class="label1">年份：</div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.year"></bk-input>
                            </div>
                        </div>
                        <div style="display: flex;margin-bottom: 10px;flex-direction: column;"
                            v-else-if="item === 'lyrics'">
                            <div style="display: flex;">
                                <div class="label1">歌词：</div>
                                <div style="width: 70%;">
                                    <bk-input :clearable="true" v-model="musicInfo.lyrics" type="textarea" :rows="15">
                                    </bk-input>
                                </div>
                                <div>
                                    <bk-icon type="arrows-right-shape" @click="translation()"
                                        style="cursor: pointer;color: #64c864;margin-left: 20px;">
                                    </bk-icon>
                                </div>
                            </div>
                            <div style="display: flex;margin-top: 10px;">
                                <div class="label1">保存歌词：</div>
                                <bk-switcher v-model="musicInfo.is_save_lyrics_file"></bk-switcher>
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'comment'">
                            <div class="label1">描述：</div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.comment" type="textarea"></bk-input>
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'album_img'">
                            <div class="label1">专辑封面：</div>
                            <div style="display: flex;flex-direction: column;">
                                <div style="width: 70%;display: flex;flex-direction: column;" v-if="reloadImg">
                                    <div>
                                        <bk-upload
                                            :files="files1"
                                            :theme="'picture'"
                                            :multiple="false"
                                            :with-credentials="true"
                                            :header="uploadHeader"
                                            :handle-res-code="handleRes"
                                            :size="{ maxFileSize: 5, maxImgSize: 5 }"
                                            :url="uploadUrl"
                                            name="upload_file"
                                        ></bk-upload>
                                    </div>
                                    <div style="color: #63656e;font-size: 12px;display: flex;">
                                        <div>({{ musicInfo.artwork_w }}*{{ musicInfo.artwork_h }})</div>
                                        <div>{{ musicInfo.artwork_size }}MB</div>
                                    </div>
                                </div>
                                <div style="display: flex;margin-top: 10px;">
                                    <div class="label1">保存图片：</div>
                                    <bk-switcher v-model="musicInfo.is_save_album_cover"></bk-switcher>
                                </div>
                            </div>
                        </div>
                        <div class="edit-item can-copy" v-else-if="item === 'discnumber'">
                            <div class="label1" v-bk-tooltips="'变量名:${discnumber}'" v-bk-copy="'${discnumber}'">光盘编号：</div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.discnumber"></bk-input>
                            </div>
                        </div>
                        <div class="edit-item can-copy" v-else-if="item === 'tracknumber'">
                            <div class="label1" v-bk-tooltips="'变量名:${tracknumber}'" v-bk-copy="'${tracknumber}'">音轨号：</div>
                            <div style="width: 70%;">
                                <bk-input :clearable="true" v-model="musicInfo.tracknumber"></bk-input>
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'duration'">
                            <div class="label1">时长：</div>
                            <div style="width: 70%;color: #63656e;font-size: 14px;">
                                {{ musicInfo.duration }} s
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'bit_rate'">
                            <div class="label1">比特率：</div>
                            <div style="width: 70%;color: #63656e;font-size: 14px;">
                                {{ musicInfo.bit_rate }} kbps
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'size'">
                            <div class="label1">文件大小：</div>
                            <div style="width: 70%;color: #63656e;font-size: 14px;">
                                {{ musicInfo.size }} MB
                            </div>
                        </div>
                        <div class="edit-item" v-else-if="item === 'album_type'">
                            <div class="label1">专辑类型：</div>
                            <div style="width: 70%;">
                                <bk-select
                                    :disabled="false"
                                    v-model="musicInfo.album_type"
                                    style="width: 250px;background: #fff;"
                                    ext-cls="select-custom"
                                    ext-popover-cls="select-popover-custom"
                                    :placeholder="'请选择专辑类型'"
                                    searchable>
                                    <bk-option v-for="option in albumTypeList"
                                        :key="option.id"
                                        :id="option.id"
                                        :name="option.name">
                                    </bk-option>
                                </bk-select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </transition>
    </div>

    <!-- 目录树浏览弹窗 -->
    <bk-dialog
        v-model="dirBrowserVisible"
        title="选择文件目录"
        :width="650"
        :mask-close="true"
        @confirm="confirmDirBrowser">
        <div v-bkloading="{ isLoading: dirBrowserLoading }">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 12px; color: #63656e; margin-right: 8px; white-space: nowrap;">快捷位置:</span>
                <bk-button size="small" :outline="true" @click="loadDirTreeRoot('/app/media')" style="margin-right: 6px;">/app/media</bk-button>
                <bk-button size="small" :outline="true" @click="loadDirTreeRoot('/app')" style="margin-right: 6px;">/app</bk-button>
                <bk-button size="small" :outline="true" @click="loadDirTreeRoot('/')" style="margin-right: 6px;">根目录 /</bk-button>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: #f0f5ff; border: 1px solid #c0d8ff; border-radius: 4px; margin-bottom: 10px; font-size: 12px;">
                <div style="display: flex; align-items: center; overflow: hidden; flex: 1; margin-right: 10px;">
                    <span style="color: #63656e; margin-right: 6px; white-space: nowrap;">当前选中:</span>
                    <span style="color: #3a84ff; font-weight: bold; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ selectedBrowserPath || '请在下方选择文件夹' }}</span>
                </div>
                <bk-button size="small" theme="primary" :disabled="!selectedBrowserPath" @click="confirmDirBrowser">进入此目录</bk-button>
            </div>
            <div class="dir-tree-box" style="height: 380px; overflow-y: auto; border: 1px solid #dcdee5; border-radius: 4px; padding: 8px;">
                <bk-tree
                    ref="dirTreeRef"
                    :data="dirTreeData"
                    :node-key="'path'"
                    :has-border="false"
                    @on-click="handleDirTreeNodeClick"
                    @async-load-nodes="handleDirTreeAsyncLoad"
                    @on-expanded="handleDirTreeNodeExpanded">
                </bk-tree>
            </div>
        </div>
    </bk-dialog>

        <bk-dialog v-model="exampleSetting1.primary.visible"
            theme="primary"
            :mask-close="false"
            @confirm="handleBatchAuto"
            :header-position="exampleSetting1.primary.headerPosition"
            title="自动批量修改">
            <p>宽松模式: 只根据标题匹配元数据, 可能存在同名或翻唱歌曲。</p>
            <p>严格模式: 根据标题和歌手或标题和专辑匹配元数据, 准确性更高。</p>
            <bk-radio-group v-model="selectAutoMode">
                <bk-radio-button value="simple">
                    宽松模式
                </bk-radio-button>
                <bk-radio-button value="hard">
                    严格模式
                </bk-radio-button>
            </bk-radio-group>
            <div>音乐源顺序</div>
            <bk-select style="width: 250px;"
                searchable
                multiple
                show-select-all
                v-model="sourceList">
                <bk-option v-for="option in resourceListBatch"
                    :key="option.id"
                    :id="option.id"
                    :name="option.name">
                </bk-option>
            </bk-select>
        </bk-dialog>
        <bk-dialog v-model="exampleSetting2.primary.visible"
            theme="primary"
            :width="600"
            :mask-close="false"
            @confirm="handleTidy"
            :header-position="exampleSetting2.primary.headerPosition"
            title="整理分类文件夹 (按标签自动归档)">
            <div class="tidy-dialog-content">
                <!-- 1. 范围选择 -->
                <div class="tidy-form-item">
                    <div class="tidy-form-label">应用整理范围：</div>
                    <bk-radio-group v-model="tidyScope">
                        <bk-radio-button value="all">
                            当前文件夹全部歌曲 (共 {{ folderMusicTotal }} 首)
                        </bk-radio-button>
                        <bk-radio-button value="selected" :disabled="tableSelectedRows.length === 0">
                            已选中的歌曲 ({{ tableSelectedRows.length }} 首)
                        </bk-radio-button>
                    </bk-radio-group>
                    <div class="tidy-tip" v-if="tidyScope === 'selected'">仅对当前列表中勾选的 {{ tableSelectedRows.length }} 首歌曲进行归档整理</div>
                    <div class="tidy-tip" v-else>将对当前文件夹内的全部音频文件进行归档整理（共 {{ folderMusicTotal }} 首）</div>
                </div>

                <!-- 2. 根目录 -->
                <div class="tidy-form-item" style="margin-top: 14px;">
                    <div class="tidy-form-label">整理后的根目录 (文件将移动至该目录下的分类子文件夹)：</div>
                    <bk-input v-model="tidyFormData.root_path" placeholder="/app/media/"></bk-input>
                </div>

                <!-- 3. 一级与二级目录 -->
                <div style="display: flex; gap: 16px; margin-top: 14px;">
                    <div style="flex: 1;">
                        <div class="tidy-form-label">一级目录分类依据 <span style="color: #ea3636;">*</span>：</div>
                        <bk-select style="width: 100%;"
                            :clearable="false"
                            v-model="tidyFormData.first_dir">
                            <bk-option v-for="option in tidyList"
                                :key="option.id"
                                :id="option.id"
                                :name="option.name">
                            </bk-option>
                        </bk-select>
                    </div>
                    <div style="flex: 1;">
                        <div class="tidy-form-label">二级目录分类依据 (可选)：</div>
                        <bk-select style="width: 100%;"
                            :clearable="true"
                            placeholder="不分二级目录"
                            v-model="tidyFormData.second_dir">
                            <bk-option v-for="option in tidyList"
                                :key="option.id"
                                :id="option.id"
                                :name="option.name">
                            </bk-option>
                        </bk-select>
                    </div>
                </div>

                <!-- 路径预览 -->
                <div class="tidy-preview-box" style="margin-top: 12px; padding: 8px 12px; background: #f5f7fa; border-radius: 4px; font-size: 12px; color: #63656e; border: 1px dashed #dcdee5;">
                    <div><span style="font-weight: 500; color: #313238;">归档路径预览：</span><code>{{ tidyPathPreview }}</code></div>
                </div>

                <!-- 4. 高级选项 -->
                <div class="tidy-advanced-options" style="margin-top: 14px; padding-top: 12px; border-top: 1px solid #f0f1f5;">
                    <div style="margin-bottom: 8px;">
                        <bk-checkbox v-model="tidyFormData.move_lrc">
                            同步移动同名歌词文件 (.lrc)
                        </bk-checkbox>
                    </div>
                    <div style="margin-bottom: 8px; display: flex; align-items: center;">
                        <span style="font-size: 12px; color: #63656e; margin-right: 12px;">遇到目标文件已存在时：</span>
                        <bk-radio-group v-model="tidyFormData.conflict_action">
                            <bk-radio value="skip">跳过 (保留原文件)</bk-radio>
                            <bk-radio value="overwrite" style="margin-left: 16px;">覆盖目标文件</bk-radio>
                        </bk-radio-group>
                    </div>
                    <div>
                        <bk-checkbox v-model="tidyFormData.clean_empty_dir">
                            整理完成后清理变为空的源文件夹
                        </bk-checkbox>
                    </div>
                </div>
            </div>
        </bk-dialog>
        <bk-dialog v-model="exampleSetting3.primary.visible"
            theme="primary"
            :mask-close="false"
            @confirm="handleSettings"
            :header-position="exampleSetting3.primary.headerPosition"
            title="配置">
            <p>选择你的配置，浏览器会保存你的默认值</p>
            <div>标签来源</div>
            <bk-select
                :disabled="false"
                :clearable="false"
                v-model="resource"
                style="width: 200px;"
                ext-cls="select-custom"
                ext-popover-cls="select-popover-custom">
                <bk-option v-for="option in resourceList"
                    :key="option.id"
                    :id="option.id"
                    :name="option.name">
                </bk-option>
            </bk-select>
            <div>展示的字段以及顺序</div>
            <bk-select style="width: 350px;margin-top: 10px;"
                searchable
                :clearable="false"
                multiple
                display-tag
                v-model="showFields">
                <bk-option v-for="option in fieldList"
                    :key="option.id"
                    :id="option.id"
                    :name="option.name">
                </bk-option>
            </bk-select>
        </bk-dialog>

        <!-- 4. 统一批量修改弹窗 (多属性/引用/剪裁/封面) -->
        <bk-dialog v-model="batchModalVisible"
            title="批量修改音乐属性 (支持多属性/引用/剪裁/封面)"
            :width="980"
            :mask-close="false"
            :header-position="'left'">
            <div class="batch-modal-body" v-if="batchModalVisible">
                <!-- 1. 应用范围选择栏 -->
                <div class="batch-scope-bar">
                    <span class="scope-label">应用修改范围:</span>
                    <bk-radio-group v-model="batchScope">
                        <bk-radio-button value="selected" :disabled="tableSelectedRows.length === 0">
                            已选中的歌曲 ({{ tableSelectedRows.length }} 首)
                        </bk-radio-button>
                        <bk-radio-button value="all">
                            当前文件夹全部歌曲 (共 {{ folderMusicTotal }} 首)
                        </bk-radio-button>
                    </bk-radio-group>
                    <span class="scope-tip" v-if="batchScope === 'selected'">仅对列表中勾选的歌曲生效</span>
                    <span class="scope-tip" v-else>将对当前文件夹内所有支持的音频文件生效</span>
                </div>

                <!-- 2. 多字段勾选编排与激活标签 -->
                <div class="batch-field-pills-wrap">
                    <span class="pills-title">勾选要同时修改的属性 (点击切换配置)：</span>
                    <div class="batch-field-pills">
                        <div v-for="col in batchSupportedCols" :key="col.id"
                            class="field-pill-item"
                            :class="{ 'pill-active': activeBatchTab === col.id, 'pill-enabled': batchFieldsEnabled[col.id] }"
                            @click="activeBatchTab = col.id">
                            <bk-checkbox v-model="batchFieldsEnabled[col.id]" @click.native.stop></bk-checkbox>
                            <span class="pill-name">{{ col.name }}</span>
                            <span v-if="batchFieldsEnabled[col.id]" class="pill-badge-check">已启用</span>
                        </div>
                    </div>
                </div>

                <!-- 3. 当前激活字段配置卡片 -->
                <div class="batch-config-panel">
                    <!-- 3.1 封面配置面板 -->
                    <div v-if="activeBatchTab === 'album_img'" class="config-section-cover">
                        <div class="section-tip">
                            为目标歌曲批量替换专辑封面或清空内嵌封面图片：
                        </div>
                        <div style="display: flex; gap: 24px; align-items: flex-start; margin-top: 12px;">
                            <div style="width: 180px;" v-if="batchReloadImg">
                                <bk-upload
                                    :files="batchCoverFiles"
                                    :theme="'picture'"
                                    :multiple="false"
                                    :with-credentials="true"
                                    :header="uploadHeader"
                                    :handle-res-code="handleBatchCoverUploadRes"
                                    :size="{ maxFileSize: 10, maxImgSize: 10 }"
                                    :url="uploadUrl"
                                    name="upload_file">
                                </bk-upload>
                            </div>
                            <div style="flex: 1; display: flex; flex-direction: column; justify-content: center;">
                                <div style="margin-bottom: 14px;">
                                    <bk-checkbox v-model="batchConfig.album_img.is_save_album_cover">
                                        同时保存为歌曲目录下的本地封面文件 (cover.jpg)
                                    </bk-checkbox>
                                </div>
                                <div style="margin-bottom: 14px;">
                                    <bk-checkbox v-model="batchConfig.album_img.clear_cover" @change="handleClearCoverChange">
                                        清空现有封面 (移除所有目标歌曲内嵌封面)
                                    </bk-checkbox>
                                </div>
                                <div v-if="batchConfig.album_img.img_base64 && !batchConfig.album_img.clear_cover" style="margin-top: 4px;">
                                    <bk-button size="small" theme="danger" :text="true" @click="removeBatchCover">
                                        <i class="bk-icon icon-close"></i> 移除已选封面图片
                                    </bk-button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 3.2 文本属性配置面板 -->
                    <div v-else class="config-section-text">
                        <!-- 快捷场景预设 -->
                        <div class="preset-row">
                            <span class="preset-label">快捷场景预设：</span>
                            <div class="preset-btns">
                                <template v-if="activeBatchTab === 'title'">
                                    <bk-button size="small" @click="applyPreset('clean_number_prefix')">去除前置序号与符号</bk-button>
                                    <bk-button size="small" @click="applyPreset('filename_no_ext')">使用文件名(去后缀)</bk-button>
                                    <bk-button size="small" @click="applyPreset('artist_title')">歌手 - 歌名</bk-button>
                                    <bk-button size="small" @click="applyPreset('remove_brackets')">去除括号及备注</bk-button>
                                    <bk-button size="small" @click="applyPreset('underscore_to_space')">下划线转空格</bk-button>
                                </template>
                                <template v-else-if="activeBatchTab === 'tracknumber'">
                                    <bk-button size="small" @click="applyPreset('track_from_filename_prefix')">从文件名前缀提取 (01. / 185 |)</bk-button>
                                    <bk-button size="small" @click="applyPreset('track_from_multidisc')">提取碟号-曲号 (1-05)</bk-button>
                                    <bk-button size="small" @click="applyPreset('track_from_word')">提取“第X集/Track X”</bk-button>
                                    <bk-button size="small" @click="applyPreset('track_sequence')">按表格当前顺序自增 (1, 2, 3...)</bk-button>
                                </template>
                                <template v-else-if="activeBatchTab === 'discnumber'">
                                    <bk-button size="small" @click="applyPreset('disc_fixed_1')">固定碟号 1 (单碟专辑)</bk-button>
                                    <bk-button size="small" @click="applyPreset('disc_fixed_2')">固定碟号 2</bk-button>
                                    <bk-button size="small" @click="applyPreset('disc_from_filename_prefix')">从文件名前缀提取 (1-05)</bk-button>
                                    <bk-button size="small" @click="applyPreset('disc_from_folder')">从目录名提取 (CD1 / Disc 2)</bk-button>
                                </template>
                                <template v-else-if="activeBatchTab === 'filename'">
                                    <bk-button size="small" @click="applyPreset('artist_title')">歌手 - 标题</bk-button>
                                    <bk-button size="small" @click="applyPreset('track_title')">音轨号.标题</bk-button>
                                    <bk-button size="small" @click="applyPreset('underscore_to_space')">下划线转空格</bk-button>
                                </template>
                                <template v-else-if="activeBatchTab === 'artist'">
                                    <bk-button size="small" @click="applyPreset('from_albumartist')">引用专辑艺术家</bk-button>
                                    <bk-button size="small" @click="applyPreset('underscore_to_space')">下划线转空格</bk-button>
                                </template>
                                <template v-else-if="activeBatchTab === 'album'">
                                    <bk-button size="small" @click="applyPreset('from_title')">引用标题</bk-button>
                                    <bk-button size="small" @click="applyPreset('from_filename')">引用文件名(去后缀)</bk-button>
                                    <bk-button size="small" @click="applyPreset('from_folder')">引用所在目录名</bk-button>
                                </template>
                                <template v-else-if="activeBatchTab === 'albumartist'">
                                    <bk-button size="small" @click="applyPreset('from_artist')">引用艺术家</bk-button>
                                </template>
                                <template v-else>
                                    <span style="color: #979ba5; font-size: 12px;">可通过下方变量与剪裁自由组合</span>
                                </template>
                            </div>
                        </div>

                        <!-- 专有设置：音轨号格式化与自增 -->
                        <div v-if="activeBatchTab === 'tracknumber'" style="margin: 8px 0 14px 0;">
                            <div style="display: flex; align-items: center; gap: 16px; background: #f5f7fa; padding: 8px 12px; border-radius: 4px;">
                                <span style="font-size: 12px; color: #63656e; font-weight: bold;">格式化补零：</span>
                                <bk-radio-group v-model="batchConfig.tracknumber.padding">
                                    <bk-radio value="raw">纯数字 (1, 2, 185)</bk-radio>
                                    <bk-radio value="pad2">补齐两位 (01, 02)</bk-radio>
                                    <bk-radio value="pad3">补齐三位 (001, 002)</bk-radio>
                                    <bk-radio value="keep">保持原样</bk-radio>
                                </bk-radio-group>
                            </div>
                            <div v-if="batchConfig.tracknumber.mode === 'sequence'" style="display: flex; align-items: center; gap: 12px; margin-top: 8px; background: #e1ecff; padding: 8px 12px; border-radius: 4px;">
                                <span style="font-size: 12px; color: #3a84ff; font-weight: bold;">自增排序起始序号：</span>
                                <bk-input type="number" :min="1" v-model.number="batchConfig.tracknumber.seq_start" style="width: 80px;"></bk-input>
                                <span style="font-size: 12px; color: #63656e;">（将按当前表格排列顺序依次为歌曲赋予自增编号）</span>
                            </div>
                        </div>

                        <!-- 专有设置：光盘编号固定值 -->
                        <div v-if="activeBatchTab === 'discnumber' && batchConfig.discnumber.mode === 'fixed'" style="margin: 8px 0 14px 0;">
                            <div style="display: flex; align-items: center; gap: 12px; background: #f5f7fa; padding: 8px 12px; border-radius: 4px;">
                                <span style="font-size: 12px; color: #63656e; font-weight: bold;">固定光盘编号：</span>
                                <bk-input type="number" :min="1" v-model.number="batchConfig.discnumber.fixed_value" style="width: 80px;"></bk-input>
                                <span style="font-size: 12px; color: #979ba5;">（将所有目标歌曲的光盘编号统一赋为该数值，单碟专辑通常为 1）</span>
                            </div>
                        </div>

                        <!-- 模板输入框 -->
                        <div class="template-input-row">
                            <div class="input-head">
                                <span class="input-title">拼接模板 (支持输入固定字符与变量占位符)：</span>
                            </div>
                            <bk-input
                                v-model="batchConfig[activeBatchTab].template"
                                :clearable="true"
                                placeholder="例如：${filename_no_ext} 或 ${artist} - ${title}">
                            </bk-input>
                            <!-- 可点击插入变量标签 -->
                            <div class="var-tags-row">
                                <span class="var-tag-label">点击插入变量：</span>
                                <div class="var-tags-list">
                                    <span class="var-tag-btn" @click="insertVariableTag('${folder}')" title="当前歌曲所在的直接父目录名">+ 所在目录 (${folder})</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${filename_no_ext}')" title="文件名但去掉后缀名">+ 文件名(无后缀)</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${filename}')" title="完整文件名">+ 完整文件名</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${title}')" title="现有标题">+ 标题</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${artist}')" title="现有艺术家">+ 艺术家</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${album}')" title="现有专辑">+ 专辑</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${albumartist}')" title="现有专辑艺术家">+ 专辑艺术家</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${tracknumber}')" title="音轨号">+ 音轨号</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${discnumber}')" title="光盘号">+ 光盘号</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${year}')" title="年份">+ 年份</span>
                                    <span class="var-tag-btn" @click="insertVariableTag('${genre}')" title="风格">+ 风格</span>
                                </div>
                            </div>
                        </div>

                        <!-- 剪裁与清洗转换规则 -->
                        <div class="trim-config-box">
                            <div class="trim-box-title">文本剪裁与清洗规则 (可选)：</div>
                            <div class="trim-box-grid">
                                <div class="trim-field-group">
                                    <span class="trim-field-label">字符切片：</span>
                                    <span class="sub-label">去除开头前</span>
                                    <bk-input type="number" :min="0" v-model.number="batchConfig[activeBatchTab].trim_start" style="width: 65px;"></bk-input>
                                    <span class="sub-label">字，去除末尾后</span>
                                    <bk-input type="number" :min="0" v-model.number="batchConfig[activeBatchTab].trim_end" style="width: 65px;"></bk-input>
                                    <span class="sub-label">字</span>
                                </div>
                                <div class="trim-field-group">
                                    <span class="trim-field-label">文本替换：</span>
                                    <bk-input v-model="batchConfig[activeBatchTab].replace_search" placeholder="查找内容" style="width: 120px;"></bk-input>
                                    <span class="sub-label">换成</span>
                                    <bk-input v-model="batchConfig[activeBatchTab].replace_with" placeholder="替换内容 (留空删除)" style="width: 140px;"></bk-input>
                                </div>
                                <div class="trim-field-group">
                                    <span class="trim-field-label">正则替换：</span>
                                    <bk-input v-model="batchConfig[activeBatchTab].regex_search" placeholder="正则表达式 (如：^\d+\.)" style="width: 160px;"></bk-input>
                                    <span class="sub-label">换成</span>
                                    <bk-input v-model="batchConfig[activeBatchTab].regex_replace" placeholder="替换文本 (如：$1)" style="width: 120px;"></bk-input>
                                </div>
                                <div class="trim-field-group">
                                    <bk-checkbox v-model="batchConfig[activeBatchTab].strip">自动去除首尾空格 (Trim)</bk-checkbox>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 4. 实时多字段统一对比预览表格 -->
                <div class="batch-preview-container">
                    <div class="preview-header">
                        <span class="preview-title">实时对比预览 (样本前 4 首歌曲)：</span>
                        <span class="preview-tip" v-if="!hasAnyFieldEnabled" style="color: #ea3636;">
                            当前尚未勾选任何需要修改的属性，请在上方勾选开启属性
                        </span>
                    </div>

                    <div v-if="previewSampleSongs.length === 0" style="padding: 20px; text-align: center; color: #979ba5;">
                        当前列表暂无样本歌曲数据
                    </div>
                    <div v-else class="preview-table-wrap">
                        <table class="batch-preview-table">
                            <thead>
                                <tr>
                                    <th style="width: 180px;">文件名</th>
                                    <th v-for="col in enabledColsList" :key="'th-' + col.id">
                                        {{ col.name }} (原值 → 修改后)
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(song, sIdx) in previewSampleSongs" :key="'sample-' + sIdx">
                                    <td class="filename-cell" :title="song.filename">{{ song.filename }}</td>
                                    <td v-for="col in enabledColsList" :key="'td-' + col.id">
                                        <!-- 封面列预览 -->
                                        <div v-if="col.id === 'album_img'" class="preview-cover-cell">
                                            <div class="cover-thumb-box">
                                                <img v-if="song.has_cover" :src="song.cover_url" class="thumb-img" />
                                                <div v-else class="thumb-none">原无</div>
                                            </div>
                                            <span class="diff-arrow">→</span>
                                            <div class="cover-thumb-box">
                                                <span v-if="batchConfig.album_img.clear_cover" class="thumb-clear">清空</span>
                                                <img v-else-if="batchConfig.album_img.preview_url" :src="batchConfig.album_img.preview_url" class="thumb-img thumb-new" />
                                                <span v-else class="thumb-keep">保持</span>
                                            </div>
                                        </div>
                                        <!-- 文本列预览 -->
                                        <div v-else class="preview-text-cell">
                                            <span class="diff-old" :title="song[col.id] || '(空)'">{{ song[col.id] || '(空)' }}</span>
                                            <span class="diff-arrow">→</span>
                                            <span class="diff-new" :title="evaluateFieldPreview(song, col.id, sIdx) || '(空)'">
                                                {{ evaluateFieldPreview(song, col.id, sIdx) || '(空)' }}
                                            </span>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- 自定义弹窗底部操作区 -->
            <template slot="footer">
                <div class="batch-dialog-footer">
                    <div class="footer-left-info">
                        <span>当前目标共计：<strong>{{ targetSongsCount }}</strong> 首歌曲</span>
                    </div>
                    <div class="footer-right-btns">
                        <bk-button @click="batchModalVisible = false">取消</bk-button>
                        <bk-button
                            theme="primary"
                            :loading="isBatchSubmitting"
                            :disabled="!hasAnyFieldEnabled || targetSongsCount === 0"
                            @click="handleConfirmMultiBatch"
                            style="margin-left: 10px;">
                            确认同时修改 ({{ targetSongsCount }} 首)
                        </bk-button>
                    </div>
                </div>
            </template>
        </bk-dialog>

        <!-- 5. 任务列表与状态管理弹窗 -->
        <bk-dialog v-model="taskDrawerVisible"
            title="任务执行记录与状态监控"
            :width="1020"
            :show-footer="false"
            :header-position="'left'">
            <div class="task-panel-wrap" v-bkloading="{ isLoading: isTaskLoading }">
                <!-- 顶部汇总统计卡片 -->
                <div class="task-stats-cards">
                    <div class="stat-card" :class="{ 'stat-active': taskFilterState === '' }" @click="filterTaskByState('')">
                        <div class="stat-num">{{ taskStats.total }}</div>
                        <div class="stat-label">全部记录</div>
                    </div>
                    <div class="stat-card stat-failed" :class="{ 'stat-active': taskFilterState === 'failed' }" @click="filterTaskByState('failed')">
                        <div class="stat-num">{{ taskStats.failed }}</div>
                        <div class="stat-label">失败任务</div>
                    </div>
                    <div class="stat-card stat-running" :class="{ 'stat-active': taskFilterState === 'running' }" @click="filterTaskByState('running')">
                        <div class="stat-num">{{ taskStats.running + taskStats.wait }}</div>
                        <div class="stat-label">进行中 / 排队</div>
                    </div>
                    <div class="stat-card stat-success" :class="{ 'stat-active': taskFilterState === 'success' }" @click="filterTaskByState('success')">
                        <div class="stat-num">{{ taskStats.success }}</div>
                        <div class="stat-label">已成功</div>
                    </div>
                </div>

                <!-- 筛选与操作工具栏 -->
                <div class="task-panel-toolbar">
                    <div class="toolbar-left">
                        <bk-radio-group v-model="taskFilterState" @change="handleTaskFilterChange">
                            <bk-radio-button value="">全部</bk-radio-button>
                            <bk-radio-button value="failed">仅看失败</bk-radio-button>
                            <bk-radio-button value="running">进行中 / 排队</bk-radio-button>
                            <bk-radio-button value="success">成功</bk-radio-button>
                        </bk-radio-group>
                        <bk-select v-model="taskFilterBatch" style="width: 175px; margin-left: 10px;" placeholder="筛选指定批次" :clearable="true" @change="loadTaskRecords(1)">
                            <bk-option v-for="b in taskStats.batches" :key="b" :id="b" :name="formatBatchTime(b)"></bk-option>
                        </bk-select>
                        <bk-input v-model="taskSearchWord" placeholder="搜索歌曲名/文件名" style="width: 180px; margin-left: 10px;" :clearable="true" @enter="loadTaskRecords(1)" @clear="loadTaskRecords(1)"></bk-input>
                    </div>
                    <div class="toolbar-right">
                        <bk-button size="small" theme="primary" :outline="true" @click="loadTaskRecords(1)">
                            <bk-icon type="refresh"></bk-icon> 刷新
                        </bk-button>
                        <bk-button size="small" theme="primary" :outline="true" v-if="taskStats.running + taskStats.wait > 0 && !isBatchSubmitting" @click="handleResumePending" style="margin-left: 6px;">
                            <bk-icon type="play"></bk-icon> 继续排队任务 ({{ taskStats.running + taskStats.wait }})
                        </bk-button>
                        <bk-button size="small" theme="warning" :outline="true" v-if="taskStats.failed > 0" @click="handleRetryAllFailed" style="margin-left: 6px;">
                            重试失败 ({{ taskStats.failed }})
                        </bk-button>
                        <bk-button size="small" theme="danger" :text="true" @click="handleClearTasks" style="margin-left: 6px;">
                            清空记录
                        </bk-button>
                    </div>
                </div>

                <!-- 任务表格 -->
                <bk-table :data="taskRecords" size="small" :outer-border="true" max-height="420" style="margin-top: 10px;">
                    <bk-table-column label="状态" width="95" align="center">
                        <template slot-scope="props">
                            <span v-if="props.row.state === 'success'" class="batch-status-badge status-success">成功</span>
                            <span v-else-if="props.row.state === 'failed'" class="batch-status-badge status-failed">失败</span>
                            <span v-else-if="props.row.state === 'running'" class="batch-status-badge status-running"><i class="bk-icon icon-circle-2-1 spin-icon"></i> 处理中</span>
                            <span v-else class="batch-status-badge status-wait">等待中</span>
                        </template>
                    </bk-table-column>
                    <bk-table-column prop="filename" label="歌曲 / 文件名" min-width="180" :show-overflow-tooltip="true">
                        <template slot-scope="props">
                            <span :title="props.row.full_path">{{ props.row.filename || props.row.song_name }}</span>
                        </template>
                    </bk-table-column>
                    <bk-table-column label="任务类型" width="100" align="center">
                        <template slot-scope="props">
                            <span class="task-type-tag" :class="props.row.tag_source === 'manual_update' ? 'type-manual' : (props.row.tag_source === 'tidy_folder' ? 'type-tidy' : 'type-auto')">
                                {{ props.row.tag_source === 'manual_update' ? '批量修改' : (props.row.tag_source === 'tidy_folder' ? '分类整理' : '自动刮削') }}
                            </span>
                        </template>
                    </bk-table-column>
                    <bk-table-column prop="batch_time" label="时间" width="150" align="center"></bk-table-column>
                    <bk-table-column prop="extra" label="执行结果 / 失败详情" min-width="220" :show-overflow-tooltip="true">
                        <template slot-scope="props">
                            <span v-if="props.row.state === 'failed'" style="color: #ea3636; font-size: 12px; font-weight: 500;">
                                <i class="bk-icon icon-close-circle-shape" style="margin-right: 3px;"></i>{{ props.row.extra || '未知错误导致保存失败' }}
                            </span>
                            <span v-else-if="props.row.state === 'success'" style="color: #2dcb56; font-size: 12px;">
                                正常完成
                            </span>
                            <span v-else style="color: #979ba5; font-size: 12px;">{{ props.row.extra || '排队中...' }}</span>
                        </template>
                    </bk-table-column>
                    <bk-table-column label="操作" width="80" align="center">
                        <template slot-scope="props">
                            <bk-button :text="true" theme="primary" size="small" v-if="props.row.state === 'failed'" @click="handleRetrySingle(props.row)">
                                重试
                            </bk-button>
                            <span v-else style="color: #c4c6cc;">-</span>
                        </template>
                    </bk-table-column>
                </bk-table>

                <!-- 分页 -->
                <div class="task-pagination-wrap" v-if="taskTotalCount > 0">
                    <bk-pagination
                        size="small"
                        :current.sync="taskCurrentPage"
                        :count="taskTotalCount"
                        :limit="taskPageSize"
                        :limit-list="[10, 20, 50, 100]"
                        @change="handleTaskPageChange"
                        @limit-change="handleTaskLimitChange">
                    </bk-pagination>
                </div>
            </div>
        </bk-dialog>

        <!-- 6. 智能规划发起弹窗 -->
        <bk-dialog v-model="aiPlanDialogVisible"
            title="⚡ 智能批量规划"
            :width="780"
            :mask-close="false"
            :header-position="'left'">
            <div class="ai-plan-dialog-body" v-if="aiPlanDialogVisible">
                <!-- 目标路径提示 -->
                <div class="ai-plan-target-banner">
                    <span class="target-title"><bk-icon type="folder-open" style="margin-right: 4px;"></bk-icon>目标目录：</span>
                    <span class="target-path" :title="filePath">{{ filePath || '未选择目录' }}</span>
                    <span class="target-count" v-if="aiPlanForm.scope === 'selected'">（已勾选 {{ tableSelectedRows.length }} 首）</span>
                    <span class="target-count" v-else>（当前目录共 {{ folderMusicTotal }} 首）</span>
                </div>

                <!-- 模式选择卡片 -->
                <div class="ai-section">
                    <div class="ai-section-title">选择规划模式：</div>
                    <div class="ai-mode-cards">
                        <div class="ai-mode-card"
                            :class="{ 'mode-active': aiPlanForm.mode === 'course' }"
                            @click="handleAiModeChange('course')">
                            <div class="mode-header">
                                <span class="mode-icon">📚</span>
                                <span class="mode-name">得到课程 / 知识专栏 / 有声书</span>
                                <span class="mode-badge" v-if="aiPlanForm.mode === 'course'">当前激活</span>
                            </div>
                            <div class="mode-desc">
                                自动从目录名智能解析讲师与专栏名，按序补全2位音轨号（00, 01...），剥离前置序号及期号广告，自动关联并内嵌本地 cover.jpg 封面。
                            </div>
                        </div>

                        <div class="ai-mode-card"
                            :class="{ 'mode-active': aiPlanForm.mode === 'music' }"
                            @click="handleAiModeChange('music')">
                            <div class="mode-header">
                                <span class="mode-icon">🎵</span>
                                <span class="mode-name">流行音乐 / 专辑歌曲</span>
                                <span class="mode-badge" v-if="aiPlanForm.mode === 'music'">当前激活</span>
                            </div>
                            <div class="mode-desc">
                                自动化剥离广告字符、无用前后缀序号，聚合多音源智能比对检索官方歌曲、歌手、专辑与正规音轨号，生成高质打标方案。
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 作用范围 -->
                <div class="ai-section" style="margin-top: 14px;">
                    <div class="ai-section-title">应用范围：</div>
                    <bk-radio-group v-model="aiPlanForm.scope">
                        <bk-radio value="all">当前文件夹全部歌曲 (共 {{ folderMusicTotal }} 首)</bk-radio>
                        <bk-radio value="selected" :disabled="tableSelectedRows.length === 0" style="margin-left: 20px;">
                            仅针对当前已选中的歌曲 (已选 {{ tableSelectedRows.length }} 首)
                        </bk-radio>
                    </bk-radio-group>
                </div>

                <!-- 提示词模板绑定 -->
                <div class="ai-section" style="margin-top: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <div class="ai-section-title" style="margin-bottom: 0;">提示词模板：</div>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <a href="javascript:;" @click="openPromptManager" style="font-size: 12px; color: #3a84ff;">
                                <bk-icon type="cog"></bk-icon> 管理模板库
                            </a>
                            <a href="javascript:;" @click="aiPlanForm.showCustomPrompt = !aiPlanForm.showCustomPrompt" style="font-size: 12px; color: #63656e;">
                                {{ aiPlanForm.showCustomPrompt ? '收起提示词细节' : '展开/微调本次提示词' }}
                            </a>
                        </div>
                    </div>
                    <select v-model="aiPlanForm.templateId" @change="handleAiTemplateChange(aiPlanForm.templateId)" class="ai-template-select">
                        <option v-for="itemTpl in currentModeTemplates" :key="itemTpl.id" :value="itemTpl.id">
                            {{ itemTpl.name }} {{ itemTpl.isDefault ? '（默认预设）' : '' }}
                        </option>
                    </select>
                </div>

                <!-- 展开编辑提示词 -->
                <div v-if="aiPlanForm.showCustomPrompt" class="ai-custom-prompt-wrap">
                    <div style="font-size: 12px; color: #63656e; margin-bottom: 4px;">微调规划要求（支持自然语言补充特殊规则）：</div>
                    <textarea
                        v-model="aiPlanForm.userPrompt"
                        rows="4"
                        class="ai-prompt-textarea"
                        placeholder="输入本次规划的特定指示，如：跳过发刊词，将作者统一设为XXX...">
                    </textarea>
                </div>

                <!-- 执行引擎与大模型状态指示条 -->
                <div class="ai-engine-banner">
                    <div class="engine-info">
                        <template v-if="aiConfig && (aiConfig.model || aiConfig.apiKey)">
                            <span class="engine-status engine-llm">🤖 大模型增强模式</span>
                            <span class="engine-model-tag">{{ aiConfig.model || 'gpt-4o-mini' }}</span>
                            <span class="engine-tip">（规则初筛 + LLM 语义纠错）</span>
                        </template>
                        <template v-else>
                            <span class="engine-status engine-local">⚡ 极速本地规则引擎</span>
                            <span class="engine-tip">（零网络依赖 / 毫秒级生成 / 零费用）</span>
                        </template>
                    </div>
                    <a href="javascript:;" @click="openAiSettings" class="engine-config-link">
                        <bk-icon type="key"></bk-icon> {{ (aiConfig && (aiConfig.apiKey || aiConfig.model)) ? '修改配置' : '配置模型 API' }}
                    </a>
                </div>
            </div>
            <template slot="footer">
                <div style="display: flex; justify-content: flex-end; align-items: center; width: 100%;">
                    <bk-button @click="aiPlanDialogVisible = false" style="margin-right: 10px;">取消</bk-button>
                    <bk-button
                        theme="primary"
                        :loading="isAiPlanning"
                        :disabled="!filePath || (aiPlanForm.scope === 'selected' && tableSelectedRows.length === 0)"
                        @click="startAiPlan">
                        <bk-icon type="data-shape" style="margin-right: 4px;" v-if="!isAiPlanning"></bk-icon>
                        {{ isAiPlanning ? '正在分析规划中...' : '开始智能规划' }}
                    </bk-button>
                </div>
            </template>
        </bk-dialog>

        <!-- 7. 规划结果审查与差异确认弹窗 (Human-in-the-Loop) -->
        <bk-dialog v-model="planReviewDialogVisible"
            title="📋 智能规划结果审查与确认"
            :width="1180"
            :mask-close="false"
            :header-position="'left'">
            <div class="plan-review-body" v-if="planReviewDialogVisible">
                <!-- 顶部信息摘要条 -->
                <div class="plan-summary-bar">
                    <div class="summary-left">
                        <div class="summary-meta-item">
                            <span class="meta-label">目录：</span>
                            <span class="meta-val" :title="aiPlanResult.dir_path">{{ aiPlanResult.dir_path }}</span>
                        </div>
                        <div class="summary-meta-item" v-if="(aiPlanResult.summary && aiPlanResult.summary.detected_album) || (aiPlanResult.course_info && aiPlanResult.course_info.course_title)">
                            <span class="meta-label">识别专辑/专栏：</span>
                            <span class="meta-val highlight">{{ (aiPlanResult.summary && aiPlanResult.summary.detected_album) || (aiPlanResult.course_info && aiPlanResult.course_info.course_title) }}</span>
                            <span class="meta-sub" v-if="(aiPlanResult.summary && aiPlanResult.summary.detected_artist) || (aiPlanResult.course_info && aiPlanResult.course_info.author)">（讲师: {{ (aiPlanResult.summary && aiPlanResult.summary.detected_artist) || (aiPlanResult.course_info && aiPlanResult.course_info.author) }}）</span>
                        </div>
                        <div class="summary-meta-item" v-if="(aiPlanResult.summary && aiPlanResult.summary.detected_cover) || aiPlanResult.album_cover_path">
                            <span class="meta-badge badge-cover">🖼️ 发现本地封面: cover.jpg</span>
                        </div>
                    </div>
                    <div class="summary-right">
                        <div class="summary-stat-pill">
                            已勾选 <strong>{{ planReviewSelectedCount }}</strong> / {{ planReviewItems.length }} 首
                        </div>
                    </div>
                </div>

                <!-- 快捷操作与筛选栏 -->
                <div class="plan-toolbar-bar">
                    <div class="plan-tools-left">
                        <bk-checkbox :value="isAllPlanReviewSelected" @change="togglePlanSelectAll" style="margin-right: 12px;">
                            全选当前列表
                        </bk-checkbox>
                        <span class="toolbar-sep">|</span>
                        <span class="filter-label">视图筛选：</span>
                        <bk-radio-group v-model="planReviewFilter" size="small">
                            <bk-radio-button value="all">全部 ({{ planReviewItems.length }})</bk-radio-button>
                            <bk-radio-button value="changed">仅看有改动 ({{ changedPlanCount }})</bk-radio-button>
                            <bk-radio-button value="low_conf">低置信度/待注意 ({{ lowConfCount }})</bk-radio-button>
                        </bk-radio-group>
                    </div>
                    <div class="plan-tools-right">
                        <bk-input
                            type="text"
                            size="small"
                            v-model="planReviewSearch"
                            placeholder="按文件名或标题过滤..."
                            :clearable="true"
                            style="width: 220px;">
                        </bk-input>
                    </div>
                </div>

                <!-- 差异审查对比表格 -->
                <div class="plan-table-wrap">
                    <table class="plan-diff-table">
                        <thead>
                            <tr>
                                <th style="width: 44px; text-align: center;">选择</th>
                                <th style="width: 65px; text-align: center;">音轨号</th>
                                <th style="width: 270px;">规划标题 (Title)</th>
                                <th style="width: 140px;">艺术家 (Artist)</th>
                                <th style="width: 160px;">专辑 (Album)</th>
                                <th style="width: 90px; text-align: center;">封面</th>
                                <th style="width: 160px;">规划依据 / 清理项</th>
                                <th style="width: 65px; text-align: center;">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="item in planReviewItemsFiltered" :key="item.filename" :class="{ 'row-unselected': !item.selected, 'row-edited': item.isEdited }">
                                <!-- Checkbox -->
                                <td style="text-align: center;">
                                    <bk-checkbox v-model="item.selected"></bk-checkbox>
                                </td>
                                <!-- Tracknumber -->
                                <td style="text-align: center;">
                                    <input
                                        v-model="item.tracknumber"
                                        @input="item.isEdited = true"
                                        class="plan-cell-input plan-track-input"
                                        placeholder="01" />
                                </td>
                                <!-- Title (with original title diff hint) -->
                                <td>
                                    <div class="plan-title-col">
                                        <input
                                            v-model="item.title"
                                            @input="item.isEdited = true"
                                            class="plan-cell-input plan-title-input" />
                                        <div class="plan-orig-hint" v-if="item.original && item.original.title && item.original.title !== item.title" :title="'原标题: ' + item.original.title">
                                            原: {{ item.original.title }}
                                        </div>
                                        <div class="plan-file-hint" :title="item.filename">
                                            📄 {{ item.filename }}
                                        </div>
                                    </div>
                                </td>
                                <!-- Artist -->
                                <td>
                                    <input
                                        v-model="item.artist"
                                        @input="item.isEdited = true"
                                        class="plan-cell-input"
                                        placeholder="艺术家" />
                                </td>
                                <!-- Album -->
                                <td>
                                    <input
                                        v-model="item.album"
                                        @input="item.isEdited = true"
                                        class="plan-cell-input"
                                        placeholder="专辑名" />
                                </td>
                                <!-- Cover -->
                                <td style="text-align: center;">
                                    <span v-if="item.album_img" class="badge-cover-yes" title="内嵌本地 cover.jpg">
                                        cover.jpg
                                    </span>
                                    <span v-else class="badge-cover-none">无</span>
                                </td>
                                <!-- Reason & Cleanups -->
                                <td>
                                    <div class="plan-cleanups-wrap">
                                        <div class="conf-badge-row">
                                            <span class="conf-tag" :class="getConfidenceClass(item.confidence)">
                                                {{ Math.round((item.confidence || 1) * 100) }}% 置信
                                            </span>
                                        </div>
                                        <div class="cleanup-pills" v-if="item.cleanups && item.cleanups.length">
                                            <span class="cleanup-pill" v-for="(c, cIdx) in item.cleanups" :key="cIdx" :title="c">{{ c }}</span>
                                        </div>
                                        <div class="plan-reason-text" v-else-if="item.reason" :title="item.reason">
                                            {{ item.reason }}
                                        </div>
                                    </div>
                                </td>
                                <!-- Action -->
                                <td style="text-align: center;">
                                    <bk-button size="small" :text="true" @click="resetPlanItem(item)" title="还原为原音频标签">
                                        还原
                                    </bk-button>
                                </td>
                            </tr>
                            <tr v-if="planReviewItemsFiltered.length === 0">
                                <td colspan="8" style="text-align: center; color: #979ba5; padding: 30px 0;">
                                    没有匹配筛选条件的规划项
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <template slot="footer">
                <div class="plan-review-footer">
                    <div class="review-footer-left" style="display: flex; align-items: center;">
                        <span>准备提交 <strong>{{ planReviewSelectedCount }}</strong> 首歌曲修改至后台任务中心</span>
                        <bk-button size="small" theme="success" :outline="true" @click="openCourseCoverDialog" style="margin-left: 12px; height: 26px; line-height: 24px;">
                            <bk-icon type="image" style="margin-right: 4px;"></bk-icon>🎨 制作专属课程封面
                        </bk-button>
                    </div>
                    <div class="review-footer-right">
                        <bk-button @click="planReviewDialogVisible = false" style="margin-right: 10px;">放弃本次规划</bk-button>
                        <bk-button
                            theme="primary"
                            :loading="isAiSubmitting"
                            :disabled="planReviewSelectedCount === 0"
                            @click="submitAiPlanExecution">
                            <bk-icon type="check" style="margin-right: 4px;" v-if="!isAiSubmitting"></bk-icon>
                            一键提交至任务中心并执行 ({{ planReviewSelectedCount }} 首)
                        </bk-button>
                    </div>
                </div>
            </template>
        </bk-dialog>

        <!-- 8. 提示词模板管理弹窗 -->
        <bk-dialog v-model="promptManagerVisible"
            title="⚙️ 提示词模板管理 (模式绑定与预设)"
            :width="880"
            :mask-close="false"
            :header-position="'left'">
            <div class="prompt-manager-body" v-if="promptManagerVisible">
                <!-- 左侧模板列表 -->
                <div class="pm-left-col">
                    <div class="pm-list-header">
                        <span>模板列表 ({{ promptTemplates.length }})</span>
                        <bk-button size="small" theme="primary" :text="true" @click="addNewPrompt">
                            <bk-icon type="plus"></bk-icon> 新建
                        </bk-button>
                    </div>
                    <div class="pm-list-scroll">
                        <div v-for="pTpl in promptTemplates" :key="pTpl.id"
                            class="pm-tpl-item"
                            :class="{ 'tpl-active': editingPrompt.id === pTpl.id }"
                            @click="selectPromptToEdit(pTpl)">
                            <div class="pm-item-top">
                                <span class="pm-tpl-name">{{ pTpl.name }}</span>
                                <span class="pm-mode-tag" :class="pTpl.mode">{{ pTpl.mode === 'course' ? '课程' : '音乐' }}</span>
                            </div>
                            <div class="pm-item-bottom">
                                <span v-if="pTpl.isDefault" class="pm-default-badge">★ 默认预设</span>
                                <span v-if="pTpl.isBuiltin" class="pm-builtin-badge">系统预置</span>
                                <span v-else class="pm-custom-badge">自定义</span>
                            </div>
                        </div>
                    </div>
                    <div class="pm-list-footer">
                        <bk-button size="small" :outline="true" @click="resetPromptDefaults" style="width: 100%;">
                            恢复所有系统默认预设
                        </bk-button>
                    </div>
                </div>

                <!-- 右侧编辑表单 -->
                <div class="pm-right-col" v-if="editingPrompt">
                    <div class="pm-form-row">
                        <label class="pm-label">模板名称：</label>
                        <bk-input v-model="editingPrompt.name" placeholder="请输入模板名称" style="width: 100%;"></bk-input>
                    </div>
                    <div class="pm-form-row" style="display: flex; gap: 20px; align-items: center;">
                        <div style="flex: 1;">
                            <label class="pm-label">适用模式：</label>
                            <bk-radio-group v-model="editingPrompt.mode">
                                <bk-radio value="course">得到课程/有声书</bk-radio>
                                <bk-radio value="music">流行音乐</bk-radio>
                            </bk-radio-group>
                        </div>
                        <div style="flex: 1; padding-top: 18px;">
                            <bk-checkbox v-model="editingPrompt.isDefault">
                                设为该模式的默认推荐模板
                            </bk-checkbox>
                        </div>
                    </div>
                    <div class="pm-form-row">
                        <label class="pm-label">系统提示词 (System Prompt)：</label>
                        <textarea v-model="editingPrompt.systemPrompt" rows="3" class="pm-textarea" placeholder="输入大模型系统角色设定..."></textarea>
                    </div>
                    <div class="pm-form-row">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <label class="pm-label" style="margin-bottom: 0;">用户提示词 (User Prompt) 模板：</label>
                            <span style="font-size: 11px; color: #979ba5;">可用变量占位符：{dir_name}, {files}</span>
                        </div>
                        <textarea v-model="editingPrompt.userPrompt" rows="7" class="pm-textarea" placeholder="输入详细的规划指导要求..."></textarea>
                    </div>
                    <div class="pm-actions-bar">
                        <bk-button
                            v-if="!editingPrompt.isBuiltin"
                            theme="danger"
                            size="small"
                            :outline="true"
                            @click="deleteCurrentPrompt">
                            删除此模板
                        </bk-button>
                        <span v-else style="font-size: 12px; color: #979ba5;">系统内置模板不可删除，但可微调保存</span>
                        <bk-button theme="primary" size="small" @click="saveEditingPrompt" style="margin-left: auto;">
                            保存模板修改
                        </bk-button>
                    </div>
                </div>
            </div>
            <template slot="footer">
                <bk-button theme="default" @click="promptManagerVisible = false">关闭</bk-button>
            </template>
        </bk-dialog>

        <!-- 9. 模型与 API 密钥设置弹窗 -->
        <bk-dialog v-model="aiSettingsVisible"
            title="🔑 模型与 API 密钥配置 (OpenAI 兼容)"
            :width="640"
            :mask-close="false"
            :header-position="'left'">
            <div class="ai-settings-body" v-if="aiSettingsVisible">
                <div class="ai-settings-notice">
                    <bk-icon type="info-circle-shape" style="margin-right: 6px; color: #3a84ff;"></bk-icon>
                    支持任何 OpenAI 兼容协议接口（如 OpenAI, DeepSeek, Moonshot, 通义千问, Ollama, OneAPI 等）。若留空，系统自动使用极速纯本地规则引擎。
                </div>

                <div class="ai-setting-row">
                    <label class="ai-setting-label">API 基础地址 (Base URL)：</label>
                    <bk-input v-model="aiConfig.baseUrl" placeholder="https://api.openai.com/v1 或 https://api.deepseek.com/v1"></bk-input>
                    <div class="ai-setting-tip">本地 Ollama 可填：<code>http://localhost:11434/v1</code> 或 <code>http://host.docker.internal:11434/v1</code></div>
                </div>

                <div class="ai-setting-row">
                    <label class="ai-setting-label">API 密钥 (API Key)：</label>
                    <bk-input type="password" v-model="aiConfig.apiKey" placeholder="sk-... (Ollama等本地模型可留空)" :clearable="true"></bk-input>
                    <div class="ai-setting-tip">API Key 仅安全存储于您浏览器的本地 localStorage 中。本地部署模型（如 Ollama）可直接留空。</div>
                </div>

                <div class="ai-setting-row">
                    <label class="ai-setting-label">模型名称 (Model Name)：</label>
                    <bk-input v-model="aiConfig.model" placeholder="例如：qwen3.8:27b-mlx, gpt-4o-mini, deepseek-chat"></bk-input>
                </div>

                <div class="ai-setting-row">
                    <label class="ai-setting-label">温度参数 (Temperature)：</label>
                    <bk-input type="number" v-model.number="aiConfig.temperature" :min="0" :max="1" :step="0.1" style="width: 140px;"></bk-input>
                    <span class="ai-setting-tip" style="margin-left: 10px; display: inline;">推荐 0.2（输出更稳定规范）</span>
                </div>

                <!-- 连通性测试结果面板 -->
                <div v-if="aiTestStatus.tested" class="ai-test-result-box" :class="aiTestStatus.success ? 'test-success' : 'test-failed'">
                    <div class="result-header">
                        <bk-icon :type="aiTestStatus.success ? 'check-circle-shape' : 'close-circle-shape'" style="margin-right: 6px;"></bk-icon>
                        <span class="result-title">{{ aiTestStatus.success ? '连通性测试通过！' : '连通性测试未通过' }}</span>
                        <span v-if="aiTestStatus.latency" class="result-latency">耗时: {{ aiTestStatus.latency }}ms</span>
                    </div>
                    <div class="result-message">{{ aiTestStatus.message }}</div>
                    <div v-if="aiTestStatus.reply" class="result-reply">模型响应预览：<code>{{ aiTestStatus.reply }}</code></div>
                </div>
            </div>
            <template slot="footer">
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                    <bk-button theme="danger" :text="true" @click="clearAiConfig">
                        清空并使用纯本地引擎
                    </bk-button>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <bk-button
                            theme="default"
                            :loading="isTestingAiConnection"
                            :disabled="!aiConfig.model"
                            @click="testAiConnection"
                            title="向大模型发送探测请求，验证网络连通性及模型推理可用性">
                            <bk-icon type="wifi" style="margin-right: 4px;" v-if="!isTestingAiConnection"></bk-icon>
                            测试连通性与可用性
                        </bk-button>
                        <bk-button @click="aiSettingsVisible = false">取消</bk-button>
                        <bk-button theme="primary" @click="saveAiConfig">保存设置</bk-button>
                    </div>
                </div>
            </template>
        </bk-dialog>

        <!-- 9. 课程专属封面智能生成与排版弹窗 -->
        <bk-dialog v-model="courseCoverDialogVisible"
            title="🎨 课程专属封面制作与智能生成"
            :width="960"
            :mask-close="false"
            :header-position="'left'">
            <div class="course-cover-dialog-body" v-if="courseCoverDialogVisible">
                <!-- 左侧配置面板 -->
                <div class="cover-left-pane">
                    <div class="form-group-item">
                        <label class="form-label">当前课程目录：</label>
                        <input type="text" class="bk-form-input" :value="filePath" readonly style="background: #f5f7fa; color: #63656e;" />
                    </div>

                    <div class="form-group-row">
                        <div class="form-group-item" style="flex: 2;">
                            <label class="form-label">课程主标题：<span style="color: #ea3636;">*</span></label>
                            <input type="text" class="bk-form-input" v-model="coverForm.title" placeholder="例如：薛兆丰的经济学课" />
                        </div>
                        <div class="form-group-item" style="flex: 1; margin-left: 10px;">
                            <label class="form-label">主讲人 / 导师：</label>
                            <input type="text" class="bk-form-input" v-model="coverForm.author" placeholder="例如：薛兆丰" />
                        </div>
                    </div>

                    <div class="form-group-row">
                        <div class="form-group-item" style="flex: 1;">
                            <label class="form-label">生图渲染引擎：</label>
                            <select v-model="coverForm.engine" class="bk-form-select">
                                <option value="comfyui">ComfyUI AI 智能绘画 (MOSS-Image)</option>
                                <option value="geometric">极速几何美学引擎 (0等待 / 无需GPU)</option>
                            </select>
                        </div>
                        <div class="form-group-item" style="flex: 1; margin-left: 10px;">
                            <label class="form-label">封面排版版式：</label>
                            <select v-model="coverForm.layout" class="bk-form-select">
                                <option value="dedao_clean">🌟 官方极简专栏风（《硅谷来信》同款·推荐）</option>
                                <option value="badge_master">🎖️ 大师课典藏徽标风（带顶部徽章与下划线）</option>
                            </select>
                        </div>
                    </div>

                    <div class="form-group-row">
                        <div class="form-group-item" style="flex: 1;" v-if="coverForm.layout === 'badge_master'">
                            <label class="form-label">顶部徽章 / 分类：</label>
                            <input type="text" class="bk-form-input" v-model="coverForm.category" placeholder="得到课程 / 精品专栏 / 大师课" />
                        </div>
                        <div class="form-group-item" style="flex: 1;" :style="coverForm.layout === 'badge_master' ? 'margin-left: 10px;' : ''">
                            <label class="form-label">标题字号与视觉冲击力：</label>
                            <select v-model="coverForm.font_size" class="bk-form-select">
                                <option value="auto">⚡ 智能自适应（默认·自动匹配 120~150px 巨幅标题）</option>
                                <option value="150">🔥 巨幅满格 (150px - 硅谷来信官方同款特大号)</option>
                                <option value="130">✨ 大号饱满 (130px - 适合5~7字)</option>
                                <option value="110">🎯 中号沉稳 (110px - 适合8~10字长标题)</option>
                                <option value="90">🍃 精巧标准 (90px)</option>
                            </select>
                        </div>
                    </div>

                    <div v-if="coverForm.engine === 'comfyui'">
                        <div class="form-group-item">
                            <label class="form-label">视觉风格预设 / 提示词：</label>
                            <div class="preset-pills">
                                <span class="pill-tag" @click="setCoverPreset('科技电路')">⚡ 科技电路 (硅谷来信)</span>
                                <span class="pill-tag" @click="setCoverPreset('极简商务')">极简商务</span>
                                <span class="pill-tag" @click="setCoverPreset('暖色几何')">暖色几何</span>
                                <span class="pill-tag" @click="setCoverPreset('深邃探索')">深邃探索</span>
                                <span class="pill-tag" @click="setCoverPreset('自然治愈')">自然治愈</span>
                            </div>
                            <textarea class="bk-form-textarea" v-model="coverForm.prompt" rows="3" placeholder="描述希望的背景画面（建议简述意象或色调），系统将自动补充 8k 渲染与极简排版画质词..."></textarea>
                        </div>
                        <div class="form-group-item">
                            <label class="form-label">生图渲染精度与速度：</label>
                            <select v-model="coverForm.quality" class="bk-form-select">
                                <option value="fast">⚡ 极速出图 (768px 底图 / 12步 / 约40~70秒，推荐)</option>
                                <option value="hd">💎 超清质感 (1024px 底图 / 16步 / 约150~180秒)</option>
                            </select>
                        </div>
                        <div class="form-group-item">
                            <label class="form-label" style="display: flex; justify-content: space-between; align-items: center;">
                                <span>ComfyUI 服务地址：</span>
                                <bk-button size="small" :loading="isTestingComfyui" @click="handleTestComfyui" style="padding: 0 8px; height: 22px; font-size: 11px;">
                                    🔍 测试连通性
                                </bk-button>
                            </label>
                            <input type="text" class="bk-form-input" v-model="coverForm.comfyui_url" placeholder="http://host.docker.internal:8188 或 http://192.168.199.12:8188" />
                            <div v-if="comfyuiTestResult" :style="{ fontSize: '11px', marginTop: '4px', lineHeight: '1.4', color: comfyuiTestResult.success ? '#2dcb56' : '#ea3636' }">
                                {{ comfyuiTestResult.msg }}
                            </div>
                            <span v-else style="font-size: 11px; color: #979ba5; margin-top: 2px;">本机 Docker 访问宿主机填 http://host.docker.internal:8188；局域网 Windows 机器填 http://192.168.199.12:8188</span>
                        </div>
                    </div>

                    <div v-if="coverForm.engine === 'geometric'">
                        <div class="form-group-item">
                            <label class="form-label">几何配色主题：</label>
                            <select v-model="coverForm.style" class="bk-form-select">
                                <option value="amber_dark">沉稳暗金 (Amber Dark - 得到经典质感)</option>
                                <option value="deep_blue">理性格调 (Deep Blue - 科技与通识)</option>
                                <option value="emerald">生命翠绿 (Emerald - 医疗与成长)</option>
                                <option value="crimson">热烈赤红 (Crimson - 商业与历史)</option>
                                <option value="purple">人文紫调 (Purple - 哲学与艺术)</option>
                            </select>
                        </div>
                    </div>

                    <div style="margin-top: 15px;">
                        <bk-button theme="primary" :loading="isGeneratingCover" @click="handleGenerateCover" style="width: 100%; height: 38px; font-weight: bold;">
                            <bk-icon type="magic" style="margin-right: 4px;" v-if="!isGeneratingCover"></bk-icon>
                            {{ isGeneratingCover ? ('正在绘制全新封面 (已耗时 ' + generateCostSeconds + 's)...') : (generatedCoverBase64 ? '🔄 不满意？重新生成一张' : '⚡ 立即生成专属封面预览') }}
                        </bk-button>
                    </div>
                </div>

                <!-- 右侧预览面板 -->
                <div class="cover-right-pane">
                    <div class="cover-preview-card">
                        <div class="cover-img-box" v-if="generatedCoverBase64 || isGeneratingCover">
                            <div class="cover-loading-overlay" v-if="isGeneratingCover">
                                <bk-icon type="circle-2-1" class="spin-icon" style="font-size: 36px; color: #3a84ff; margin-bottom: 12px;"></bk-icon>
                                <span style="font-size: 13px; font-weight: bold; color: #313238;">正在渲染全新封面...</span>
                                <span style="font-size: 11px; color: #63656e; margin-top: 4px;">已耗时 {{ generateCostSeconds }} 秒 (已中断旧任务)</span>
                            </div>
                            <img v-if="generatedCoverBase64" :src="generatedCoverBase64" alt="课程封面预览" />
                        </div>
                        <div class="cover-empty-box" v-else>
                            <bk-icon type="image" style="font-size: 48px; color: #c4c6cc; margin-bottom: 12px;"></bk-icon>
                            <p style="color: #63656e; font-size: 14px; font-weight: bold; margin-bottom: 6px;">等待生成封面预览</p>
                            <span style="color: #979ba5; font-size: 12px; text-align: center; line-height: 1.5;">
                                点击左侧「立即生成」按钮查看渲染效果<br />
                                自动叠加得到级专业版式、折行标题与金色徽标
                            </span>
                        </div>

                        <div class="cover-meta-bar" v-if="generatedCoverMeta">
                            <span>引擎：<strong>{{ generatedCoverMeta.source }}</strong></span>
                            <span style="margin-left: 10px;">耗时：<strong>{{ generatedCoverMeta.cost_sec }}s</strong></span>
                            <span style="margin-left: 10px;">分辨率：<strong>1024 × 1024</strong></span>
                        </div>
                    </div>
                </div>
            </div>

            <template slot="footer">
                <div class="cover-dialog-footer">
                    <div class="cover-footer-left">
                        <label style="cursor: pointer; display: inline-flex; align-items: center; font-size: 13px; color: #63656e;">
                            <input type="checkbox" v-model="coverForm.embed_to_files" style="margin-right: 6px;" />
                            同时将封面内嵌写入该目录下所有音频标签 (ID3 / FLAC / MP4)
                        </label>
                    </div>
                    <div class="cover-footer-right">
                        <bk-button @click="courseCoverDialogVisible = false" style="margin-right: 10px;">关闭</bk-button>
                        <bk-button
                            theme="success"
                            :loading="isSavingCover"
                            :disabled="!generatedCoverBase64"
                            @click="handleApplyCover">
                            <bk-icon type="check" style="margin-right: 4px;" v-if="!isSavingCover"></bk-icon>
                            保存 cover.jpg 并应用到课程
                        </bk-button>
                    </div>
                </div>
            </template>
        </bk-dialog>
    </div>
</template>
<script>
    import {mapGetters} from 'vuex'

    export default {
        data() {
            return {
                files1: [],
                uploadUrl: '/api/upload_image/',
                uploadHeader: [
                    {name: 'X-CSRFToken', value: this.getCookie('django_vue_cli_csrftoken')},
                    {name: 'AUTHORIZATION', value: this.getCookie('AUTHORIZATION')}
                ],
                showFields: (() => {
                    const defaultFields = ['filename', 'artist', 'album', 'albumartist', 'discnumber', 'tracknumber', 'genre', 'year', 'lyrics', 'comment', 'album_img']
                    try {
                        const stored = localStorage.getItem('showFields')
                        if (stored) {
                            const list = JSON.parse(stored)
                            if (Array.isArray(list)) {
                                let changed = false
                                if (!list.includes('discnumber') || !list.includes('tracknumber')) {
                                    const idx = list.indexOf('albumartist')
                                    const insertPos = idx !== -1 ? idx + 1 : list.length
                                    const toInsert = []
                                    if (!list.includes('discnumber')) toInsert.push('discnumber')
                                    if (!list.includes('tracknumber')) toInsert.push('tracknumber')
                                    list.splice(insertPos, 0, ...toInsert)
                                    changed = true
                                }
                                if (changed) {
                                    localStorage.setItem('showFields', JSON.stringify(list))
                                }
                                return list
                            }
                        }
                    } catch (e) {}
                    return defaultFields
                })(),
                fieldList: [
                    {id: 'filename', name: '文件名'},
                    {id: 'artist', name: '艺术家'},
                    {id: 'album', name: '专辑'},
                    {id: 'album_type', name: '专辑类型'},
                    {id: 'albumartist', name: '专辑艺术家'},
                    {id: 'discnumber', name: '光盘编号'},
                    {id: 'tracknumber', name: '音轨号'},
                    {id: 'genre', name: '风格'},
                    {id: 'year', name: '年份'},
                    {id: 'lyrics', name: '歌词'},
                    {id: 'comment', name: '描述'},
                    {id: 'album_img', name: '专辑封面'},
                    {id: 'duration', name: '时长'},
                    {id: 'size', name: '文件大小'},
                    {id: 'bit_rate', name: '比特率'},
                    {id: 'language', name: '语言'}
                ],
                albumTypeList: [
                    {id: 'album;compilation', name: '合集'},
                    {id: 'album;live', name: '现场'},
                    {id: 'album;remix', name: '混音'},
                    {id: 'album;soundtrack', name: '原声'},
                    {id: 'album;demo', name: '演示'},
                    {id: 'album;album', name: '普通'},
                    {id: 'ep', name: 'EP'},
                    {id: 'single', name: '单曲'}
                ],
                searchWord: '',
                currentDirPath: localStorage.getItem('last_visited_dir') || '/app/media/',
                isEditingPath: false,
                inputFilePath: '',
                recentDirs: [],
                dirBrowserVisible: false,
                dirBrowserLoading: false,
                dirFilterWord: '',
                selectedBrowserPath: '',
                dirTreeData: [],
                treeListOne: [],
                fullPath: '',
                fileName: '',
                resource: localStorage.getItem('resource') ? localStorage.getItem('resource') : 'netease',
                translationText: '',
                resourceList: [
                    {id: 'acoustid', name: '指纹识别'},
                    {id: 'netease', name: '网易云音乐'},
                    {id: 'migu', name: '咪咕音乐'},
                    {id: 'qmusic', name: 'QQ音乐'},
                    {id: 'kugou', name: '酷狗音乐'},
                    {id: 'smart_tag', name: '智能刮削'}
                ],
                resourceListBatch: [
                    {id: 'netease', name: '网易云音乐'},
                    {id: 'migu', name: '咪咕音乐'},
                    {id: 'qmusic', name: 'QQ音乐'},
                    {id: 'kugou', name: '酷狗音乐'}
                ],
                tidyList: [
                    {id: 'title', name: '标题'},
                    {id: 'artist', name: '艺术家'},
                    {id: 'album', name: '专辑'},
                    {id: 'albumartist', name: '专辑艺术家'},
                    {id: 'album_type', name: '专辑类型'},
                    {id: 'genre', name: '风格'},
                    {id: 'language', name: '语言'},
                    {id: 'comment', name: '描述'}
                ],
                baseMusicInfo: {
                    'genre': '流行',
                    'is_save_lyrics_file': false,
                    'is_save_album_cover': false
                },
                musicInfo: {
                    'genre': '流行',
                    'is_save_lyrics_file': false,
                    'is_save_album_cover': false
                },
                musicInfoManual: {
                    'genre': '流行',
                    'is_save_lyrics_file': false,
                    'is_save_album_cover': false
                },
                fadeShowDir: false,
                fadeShowDetail: false,
                showTranslation: false,
                isLoading: false,
                SongList: [],
                reloadImg: true,
                genreList: [
                    {'id': '流行', name: '流行'},
                    {'id': '摇滚', name: '摇滚'},
                    {'id': '说唱', name: '说唱'},
                    {'id': '民谣', name: '民谣'},
                    {'id': '电子', name: '电子'},
                    {'id': '爵士', name: '爵士'},
                    {'id': '纯音乐', name: '纯音乐'},
                    {'id': '金属', name: '金属'},
                    {'id': '世界音乐', name: '世界音乐'},
                    {'id': '新世纪', name: '新世纪'},
                    {'id': '古典', name: '古典'},
                    {'id': '独立', name: '独立'},
                    {'id': '氛围音乐', name: '氛围音乐'}
                ],
                languageList: [
                    {'id': '中文', name: '中文'},
                    {'id': '英文', name: '英文'},
                    {'id': '日文', name: '日文'},
                    {'id': '韩文', name: '韩文'},
                    {'id': '泰文', name: '泰文'},
                    {'id': '未知', name: '未知'}
                ],
                checkedIds: [],
                checkedData: [],
                selectAutoMode: 'hard',
                sourceList: [],
                tidyScope: 'all',
                tidyFormData: {
                    root_path: '/app/media/',
                    first_dir: 'artist',
                    second_dir: '',
                    move_lrc: true,
                    conflict_action: 'skip',
                    clean_empty_dir: false
                },
                exampleSetting1: {
                    primary: {
                        visible: false,
                        headerPosition: 'left'
                    }
                },
                exampleSetting2: {
                    primary: {
                        visible: false,
                        headerPosition: 'left'
                    }
                },
                exampleSetting3: {
                    primary: {
                        visible: false,
                        headerPosition: 'left'
                    }
                },
                sortedField: localStorage.getItem('sortedField') ? JSON.parse(localStorage.getItem('sortedField')) : [],
                tableSize: localStorage.getItem('tableSize') || 'medium',
                tablePageSize: localStorage.getItem('tablePageSize') ? Number(localStorage.getItem('tablePageSize')) : 32,
                pageSizeList: [32, 64, 128, 256, 512, 1000],
                tablePage: 1,
                folderMusicList: [],
                folderMusicTotal: 0,
                isTableLoading: false,
                activeRightTab: 'fileList',
                isForceRefreshing: false,
                cacheBuster: 0,
                // 任务列表与监控状态
                taskDrawerVisible: false,
                isTaskLoading: false,
                taskRecords: [],
                taskTotalCount: 0,
                taskCurrentPage: 1,
                taskPageSize: 20,
                taskFilterState: '',
                taskFilterBatch: '',
                taskSearchWord: '',
                taskStats: {
                    total: 0,
                    failed: 0,
                    success: 0,
                    running: 0,
                    wait: 0,
                    batches: []
                },
                // AI 智能规划 Agent 状态
                aiPlanDialogVisible: false,
                isAiPlanning: false,
                planReviewDialogVisible: false,
                isAiSubmitting: false,
                promptManagerVisible: false,
                aiSettingsVisible: false,
                isTestingAiConnection: false,
                aiTestStatus: {
                    tested: false,
                    success: false,
                    message: '',
                    latency: 0,
                    reply: ''
                },
                // 课程封面制作与智能生成状态
                courseCoverDialogVisible: false,
                isGeneratingCover: false,
                isSavingCover: false,
                isTestingComfyui: false,
                comfyuiTestResult: null,
                generateCostSeconds: 0,
                generateTimer: null,
                generatedCoverBase64: '',
                generatedCoverMeta: null,
                coverForm: {
                    title: '',
                    author: '',
                    category: '得到课程',
                    engine: 'comfyui',
                    quality: 'fast',
                    layout: 'dedao_clean',
                    font_size: 'auto',
                    comfyui_url: localStorage.getItem('mtw_comfyui_url') || 'http://host.docker.internal:8188',
                    style: 'amber_dark',
                    prompt: 'dark navy electronic PCB circuit board background, glowing cyan neon and brushed gold copper conductive tracks, motherboard microchips, a minimalist outline envelope icon made of circuit lines at top center, clean empty dark negative space in the center, radial dark vignette, sleek modern tech graphic design, vector aesthetic, 8k, masterpiece, no text',
                    embed_to_files: true
                },
                aiPlanForm: {
                    mode: 'course',
                    scope: 'all',
                    templateId: 'tpl_course_default',
                    systemPrompt: '',
                    userPrompt: '',
                    showCustomPrompt: false
                },
                promptTemplates: [],
                editingPrompt: {
                    id: '',
                    name: '',
                    mode: 'course',
                    isDefault: false,
                    isBuiltin: false,
                    systemPrompt: '',
                    userPrompt: ''
                },
                aiConfig: {
                    apiKey: '',
                    baseUrl: 'https://api.openai.com/v1',
                    model: 'gpt-4o-mini',
                    temperature: 0.2
                },
                aiPlanResult: {
                    dir_path: '',
                    mode: '',
                    total_scanned: 0,
                    total_planned: 0,
                    album_cover_path: '',
                    course_info: null,
                    plans: []
                },
                planReviewItems: [],
                planReviewFilter: 'all',
                planReviewSearch: '',
                // 批量修改与进度跟踪状态
                batchModalVisible: false,
                isBatchSubmitting: false,
                batchScope: 'all',
                activeBatchTab: 'title',
                tableSelectedRows: [],
                batchStatusMap: {},
                currentBatchId: '',
                batchPollTimer: null,
                taskDrawerTimer: null,
                sseSource: null,
                batchReloadImg: true,
                batchCoverFiles: [],
                batchSupportedCols: [
                    { id: 'album_img', name: '封面' },
                    { id: 'filename', name: '文件名' },
                    { id: 'title', name: '标题' },
                    { id: 'artist', name: '艺术家' },
                    { id: 'album', name: '专辑' },
                    { id: 'albumartist', name: '专辑艺术家' },
                    { id: 'tracknumber', name: '音轨号' },
                    { id: 'discnumber', name: '光盘编号' },
                    { id: 'year', name: '年份' },
                    { id: 'genre', name: '风格' }
                ],
                batchFieldsEnabled: {
                    album_img: false,
                    filename: false,
                    title: false,
                    artist: false,
                    album: false,
                    albumartist: false,
                    tracknumber: false,
                    discnumber: false,
                    year: false,
                    genre: false
                },
                batchConfig: {
                    album_img: {
                        img_base64: '',
                        preview_url: '',
                        is_save_album_cover: false,
                        clear_cover: false
                    },
                    filename: {
                        template: '${artist} - ${title}',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        regex_search: '',
                        regex_replace: '',
                        strip: true
                    },
                    title: {
                        template: '${filename_no_ext}',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        regex_search: '',
                        regex_replace: '',
                        strip: true
                    },
                    artist: {
                        template: '${artist}',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        regex_search: '',
                        regex_replace: '',
                        strip: true
                    },
                    album: {
                        template: '${album}',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        regex_search: '',
                        regex_replace: '',
                        strip: true
                    },
                    albumartist: {
                        template: '${albumartist}',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        regex_search: '',
                        regex_replace: '',
                        strip: true
                    },
                    tracknumber: {
                        mode: 'extract_filename',
                        template: '${filename_no_ext}',
                        regex_search: '^(\\d+)',
                        regex_replace: '$1',
                        padding: 'raw',
                        seq_start: 1,
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        strip: true
                    },
                    discnumber: {
                        mode: 'fixed',
                        fixed_value: 1,
                        template: '1',
                        regex_search: '^(?:CD)?(\\d+)[-_.]\\d+',
                        regex_replace: '$1',
                        padding: 'raw',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        strip: true
                    },
                    year: {
                        template: '${year}',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        regex_search: '',
                        regex_replace: '',
                        strip: true
                    },
                    genre: {
                        template: '${genre}',
                        trim_start: 0,
                        trim_end: 0,
                        replace_search: '',
                        replace_with: '',
                        regex_search: '',
                        regex_replace: '',
                        strip: true
                    }
                }
            }
        },
        computed: {
            ...mapGetters(['geFullPath']),
            targetSongsCount() {
                if (this.batchScope === 'all') {
                    return this.folderMusicTotal
                }
                return this.tableSelectedRows.length
            },
            hasAnyFieldEnabled() {
                return Object.values(this.batchFieldsEnabled).some(v => v)
            },
            enabledColsList() {
                return this.batchSupportedCols.filter(col => this.batchFieldsEnabled[col.id])
            },
            previewSampleSongs() {
                if (this.tableSelectedRows.length > 0) {
                    return this.tableSelectedRows.slice(0, 4)
                }
                return this.folderMusicList.slice(0, 4)
            },
            pathSegments() {
                const raw = (this.currentDirPath || '').trim()
                const parts = raw.split('/').filter(p => p.length > 0)
                let accumulated = ''
                return parts.map(part => {
                    accumulated += '/' + part
                    return {
                        name: part,
                        path: accumulated
                    }
                })
            },
            isAtRoot() {
                return !this.currentDirPath || this.currentDirPath === '/' || this.currentDirPath === ''
            },
            currentSortLabel() {
                if (this.sortedField.includes('name')) return '文件名'
                if (this.sortedField.includes('update_time')) return '修改时间'
                if (this.sortedField.includes('size')) return '文件大小'
                return '排序'
            },
            tidyPathPreview() {
                const root = (this.tidyFormData.root_path || '/app/media/').replace(/\/+$/, '')
                const firstOpt = this.tidyList.find(o => o.id === this.tidyFormData.first_dir)
                const firstName = firstOpt ? `[${firstOpt.name}]` : '[一级分类]'
                let secondPart = ''
                if (this.tidyFormData.second_dir) {
                    const secondOpt = this.tidyList.find(o => o.id === this.tidyFormData.second_dir)
                    secondPart = `/${secondOpt ? `[${secondOpt.name}]` : '[二级分类]'}`
                }
                return `${root}/${firstName}${secondPart}/歌曲文件名.mp3`
            },
            currentModeTemplates() {
                if (!this.promptTemplates) return []
                return this.promptTemplates.filter(t => t.mode === this.aiPlanForm.mode)
            },
            planReviewItemsFiltered() {
                let list = this.planReviewItems || []
                if (this.planReviewFilter === 'changed') {
                    list = list.filter(i => {
                        const orig = i.original || {}
                        return (orig.title && orig.title !== i.title) ||
                               (orig.tracknumber && orig.tracknumber !== i.tracknumber) ||
                               (orig.artist && orig.artist !== i.artist) ||
                               (orig.album && orig.album !== i.album)
                    })
                } else if (this.planReviewFilter === 'low_conf') {
                    list = list.filter(i => (i.confidence || 1) < 0.9)
                }
                if (this.planReviewSearch) {
                    const q = this.planReviewSearch.trim().toLowerCase()
                    list = list.filter(i => (i.filename && i.filename.toLowerCase().includes(q)) || (i.title && i.title.toLowerCase().includes(q)))
                }
                return list
            },
            planReviewSelectedCount() {
                return (this.planReviewItems || []).filter(i => i.selected).length
            },
            isAllPlanReviewSelected() {
                const list = this.planReviewItemsFiltered
                return list.length > 0 && list.every(i => i.selected)
            },
            changedPlanCount() {
                return (this.planReviewItems || []).filter(i => {
                    const orig = i.original || {}
                    return (orig.title && orig.title !== i.title) ||
                           (orig.tracknumber && orig.tracknumber !== i.tracknumber) ||
                           (orig.artist && orig.artist !== i.artist) ||
                           (orig.album && orig.album !== i.album)
                }).length
            },
            lowConfCount() {
                return (this.planReviewItems || []).filter(i => (i.confidence || 1) < 0.9).length
            },
            filePath: {
                get() {
                    if (this.geFullPath) {
                        const fullPath = this.geFullPath
                        this.$store.commit('setFullPath', '')
                        this.currentDirPath = fullPath
                        return fullPath
                    }
                    return this.currentDirPath || '/app/media/'
                },
                set(value) {
                    this.currentDirPath = value
                    this.$store.commit('setFullPath', value)
                }
            }
        },
        watch: {
            taskDrawerVisible(val) {
                if (!val) {
                    this.stopTaskDrawerAutoRefresh()
                } else {
                    this.startTaskDrawerAutoRefresh()
                }
            },
            activeRightTab(val) {
                if (val === 'fileList') {
                    this.$nextTick(() => {
                        if (this.$refs.musicTable) {
                            this.$refs.musicTable.doLayout()
                        }
                    })
                }
            },
            'musicInfo.title'(val) {
                this.$nextTick(() => {
                    setTimeout(() => {
                        if (this.$refs.musicTable) {
                            this.$refs.musicTable.doLayout()
                        }
                    }, 260)
                })
            }
        },
        created() {
            try {
                const savedRecent = localStorage.getItem('music_recent_dirs')
                if (savedRecent) {
                    this.recentDirs = JSON.parse(savedRecent)
                }
            } catch (e) {}

            const lastDir = localStorage.getItem('last_visited_dir')
            if (lastDir) {
                this.currentDirPath = lastDir
            }
            this.addRecentDir(this.currentDirPath)
            this.handleSearchFile()
            this.fetchTaskStats()
            this.initEventSource()
            this.initAiAgentState()
        },
        beforeDestroy() {
            if (this.batchPollTimer) {
                clearInterval(this.batchPollTimer)
                this.batchPollTimer = null
            }
            this.stopTaskDrawerAutoRefresh()
            this.closeEventSource()
        },
        methods: {
            navigateToPath(path) {
                if (!path) return
                const clean = path.replace(/\/+$/, '') || '/'
                this.currentDirPath = clean
                this.filePath = clean
                this.isEditingPath = false
                this.tablePage = 1
                this.fileName = ''
                this.musicInfo = Object.assign({}, this.baseMusicInfo)
                this.batchStatusMap = {}
                localStorage.setItem('last_visited_dir', clean)
                this.addRecentDir(clean)
                this.fetchFolderMusicList()
            },
            navigateToSegment(idx) {
                const seg = this.pathSegments[idx]
                if (seg) {
                    this.navigateToPath(seg.path)
                }
            },
            backDir() {
                if (this.pathSegments.length > 1) {
                    this.navigateToPath(this.pathSegments[this.pathSegments.length - 2].path)
                } else {
                    this.navigateToPath('/')
                }
            },
            refreshDir() {
                this.tablePage = 1
                this.fetchFolderMusicList()
                this.$cwMessage('目录已刷新', 'success')
            },
            startEditPath() {
                this.inputFilePath = this.currentDirPath
                this.isEditingPath = true
                this.$nextTick(() => {
                    if (this.$refs.pathInputRef && this.$refs.pathInputRef.focus) {
                        this.$refs.pathInputRef.focus()
                    }
                })
            },
            cancelEditPath() {
                this.isEditingPath = false
            },
            confirmInputPath() {
                if (!this.inputFilePath) {
                    this.cancelEditPath()
                    return
                }
                this.navigateToPath(this.inputFilePath)
            },
            addRecentDir(path) {
                if (!path || path === '/') return
                const clean = path.replace(/\/+$/, '')
                let list = this.recentDirs.filter(d => d !== clean)
                list.unshift(clean)
                if (list.length > 10) {
                    list = list.slice(0, 10)
                }
                this.recentDirs = list
                try {
                    localStorage.setItem('music_recent_dirs', JSON.stringify(list))
                } catch (e) {}
            },
            selectRecentDir(path) {
                this.navigateToPath(path)
            },
            clearRecentDirs() {
                this.recentDirs = []
                try {
                    localStorage.removeItem('music_recent_dirs')
                } catch (e) {}
            },
            openDirBrowser() {
                this.dirBrowserVisible = true
                this.selectedBrowserPath = this.currentDirPath
                this.dirFilterWord = ''
                this.loadDirTreeRoot('/app/media')
            },
            loadDirTreeRoot(rootPath) {
                const target = rootPath || '/app/media'
                this.dirBrowserLoading = true
                this.$api.Task.fileList({ file_path: target, only_dir: true }).then((res) => {
                    this.dirBrowserLoading = false
                    if (res.result && res.data) {
                        this.dirTreeData = res.data
                    }
                }).catch(() => {
                    this.dirBrowserLoading = false
                })
            },
            handleDirTreeAsyncLoad(node) {
                if (!node || !node.path) return
                this.$set(node, 'loading', true)
                this.$api.Task.fileList({ file_path: node.path, only_dir: true }).then((res) => {
                    this.$set(node, 'loading', false)
                    if (res.result && res.data && res.data[0]) {
                        const children = res.data[0].children || []
                        this.$set(node, 'children', children)
                        this.$set(node, 'async', false)
                        this.$set(node, 'expanded', true)
                    }
                }).catch(() => {
                    this.$set(node, 'loading', false)
                })
            },
            handleDirTreeNodeClick(node) {
                this.selectedBrowserPath = node.path
                // 点击节点行同时触发展开/收起下钻
                if (node.async && !node.children) {
                    this.handleDirTreeAsyncLoad(node)
                } else if (node.children && node.children.length > 0) {
                    this.$set(node, 'expanded', !node.expanded)
                }
            },
            handleDirTreeNodeExpanded(node, expanded) {
                if (expanded && (!node.children || node.children.length === 0) && node.async) {
                    this.handleDirTreeAsyncLoad(node)
                }
            },
            confirmDirBrowser() {
                if (this.selectedBrowserPath) {
                    this.navigateToPath(this.selectedBrowserPath)
                }
                this.dirBrowserVisible = false
            },
            handleSearchSubmit() {
                this.tablePage = 1
                this.fetchFolderMusicList()
            },
            tpl(node, ctx) {
                // 如果在某些情况下 h 不能自动注入而报错，需将 h 参数写上；一般来说 h 默认是第一参数，但是现在改为第一参数会导致已经使用的用户都需要修改，所以先放在最后。
                // 如果 h 能自动注入则可以忽略 h 参数，无需写上，否则 h 参数会重复。
                const titleClass = node.selected ? 'node-title node-selected' : 'node-title ' + node.state
                if (node.title.length > 25) {
                    return <span>
                    <span class={titleClass} domPropsInnerHTML={node.title.slice(0, 25)}
                        onClick={() => {
                            this.nodeClickOne(node)
                        }} v-bk-tooltips={node.title}>
                    </span>
                    </span>
                } else {
                    return <span>
                    <span class={titleClass} domPropsInnerHTML={node.title.slice(0, 25)}
                        onClick={() => {
                            this.nodeClickOne(node)
                        }}>
                    </span>
                    </span>
                }
            },
            nodeClickOne(node) {
                if (node.icon === 'icon-folder') {
                    const sep = this.filePath.endsWith('/') ? '' : '/'
                    this.filePath = (this.filePath + sep + node.name).replace(/\/+/g, '/')
                    this.fileName = ''
                    this.activeRightTab = 'fileList'
                    this.tablePage = 1
                    this.fetchFolderMusicList()
                } else {
                    if (node.children && node.children.length > 0) {
                        return
                    }
                    if (this.fileName === node.name) {
                        this.closeEditSection()
                        return
                    }
                    this.loadSongDetail(node.name)
                }
            },
            loadSongDetail(name) {
                this.musicInfo = Object.assign({}, this.baseMusicInfo)
                this.fileName = name
                const cleanPath = this.filePath.replace(/\/+$/, '')
                this.fullPath = cleanPath + '/' + name
                this.$api.Task.musicId3({'file_path': cleanPath, 'file_name': name}).then((res) => {
                    if (res.result) {
                        this.musicInfo = res.data
                        this.musicInfo.is_save_lyrics_file = false
                        this.musicInfo.is_save_album_cover = false
                        this.files1 = [
                            {
                                name: 'cover.png',
                                status: 'done',
                                url: this.musicInfo.artwork
                            }
                        ]
                    } else {
                        this.$cwMessage(res.message, 'error')
                    }
                })
            },
            closeEditSection() {
                this.musicInfo = Object.assign({}, this.baseMusicInfo)
                this.fileName = ''
            },
            setTableSize(size) {
                this.tableSize = size
                localStorage.setItem('tableSize', size)
            },
            handlePageLimitChange(limit) {
                this.tablePageSize = Number(limit) || 128
                localStorage.setItem('tablePageSize', this.tablePageSize)
                this.tablePage = 1
                this.fetchFolderMusicList()
            },
            handlePageSizeChange() {
                this.tablePageSize = Number(this.tablePageSize) || 128
                localStorage.setItem('tablePageSize', this.tablePageSize)
                this.tablePage = 1
                this.fetchFolderMusicList()
            },
            handleTablePageChange(page) {
                this.tablePage = page
                this.fetchFolderMusicList()
            },
            tableRowClassName({ row }) {
                return (row.filename === this.fileName) ? 'active-table-row' : ''
            },
            handleTableRowClick(row) {
                if (this.fileName === row.filename) {
                    this.closeEditSection()
                    return
                }
                this.loadSongDetail(row.filename)
            },
            fetchFolderMusicList() {
                if (!this.filePath) return
                this.isTableLoading = true
                const params = {
                    file_path: this.filePath,
                    page: this.tablePage,
                    page_size: Number(this.tablePageSize) || 128,
                    search_word: this.searchWord || '',
                    sorted_field: this.sortedField.length > 0 ? this.sortedField[0] : ''
                }
                this.$api.Task.folderMusicList(params).then((res) => {
                    this.isTableLoading = false
                    if (res.result && res.data) {
                        this.folderMusicList = res.data.items || []
                        this.folderMusicTotal = res.data.total || 0
                        this.$nextTick(() => {
                            if (this.$refs.musicTable) {
                                this.$refs.musicTable.doLayout()
                            }
                        })
                    } else {
                        this.folderMusicList = []
                        this.folderMusicTotal = 0
                    }
                }).catch(() => {
                    this.isTableLoading = false
                })
            },
            // checkbox
            nodeCheckTwo(node, checked) {
                console.log(node, checked)
                if (checked) {
                    this.musicInfo = this.baseMusicInfo
                    if (node.children && node.children.length > 0) {
                        this.checkedData = []
                        this.checkedIds = []
                        node.children.forEach(el => {
                            this.checkedData.push({
                                checked: el.checked,
                                icon: el.icon,
                                id: el.id,
                                name: el.name,
                                title: el.title
                            })
                            this.checkedIds.push(el.id)
                        })
                    } else {
                        this.checkedData.push({
                            checked: node.checked,
                            icon: node.icon,
                            id: node.id,
                            name: node.name,
                            title: node.title
                        })
                        this.checkedIds.push(node.id)
                    }
                } else {
                    if (node.children && node.children.length > 0) {
                        this.checkedData = []
                        this.checkedIds = []
                    } else {
                        const index = this.checkedIds.indexOf(node.id)
                        if (index !== -1) {
                            this.checkedData.splice(index, 1)
                            this.checkedIds.splice(index, 1)
                        }
                    }
                }
                console.log(this.checkedIds)
            },
            handleCopy(k, v) {
                if (k === 'lyric') {
                    const resurce = this.resource !== 'smart_tag' ? this.resource : v.resource
                    this.$api.Task.fetchLyric({'song_id': v.id, 'resource': resurce}).then((res) => {
                        if (res.result) {
                            this.musicInfo['lyrics'] = res.data
                        } else {
                            this.$cwMessage('未找到歌词', 'error')
                        }
                    })
                } else if (k === 'album_img') {
                    this.musicInfo[k] = v
                    this.files1 = [
                        {
                            name: 'cover.png',
                            status: 'done',
                            url: v
                        }
                    ]
                    this.reloadImg = false
                    this.$nextTick(() => {
                        this.reloadImg = true
                    })
                } else if (k === 'lyric_tran') {
                    this.musicInfo['lyrics'] = v
                } else {
                    this.musicInfo[k] = v
                }
            },
            copyAll(item) {
                this.handleCopy('title', item.name)
                this.handleCopy('year', item.year)
                this.handleCopy('lyric', item)
                this.handleCopy('album', item.album)
                this.handleCopy('artist', item.artist)
                this.handleCopy('album_img', item.album_img)
            },
            nodeExpandedOne(node, expanded) {
            },
            // 查询网易云接口
            toggleLock(mode) {
                if (mode === 'title') {
                    if (!this.musicInfo.title) {
                        this.$cwMessage('标题不能为空', 'error')
                        return
                    }
                    this.activeRightTab = 'searchList'
                    this.showTranslation = false
                    this.fadeShowDetail = false
                    this.$api.Task.fetchId3Title({
                        title: this.musicInfo.title,
                        resource: this.resource,
                        full_path: this.fullPath
                    }).then((res) => {
                        this.fadeShowDetail = true
                        this.SongList = res.data
                    })
                }
            },
            translation() {
                if (!this.musicInfo.lyrics) {
                    this.$cwMessage('歌词不能为空', 'error')
                    return
                }
                this.activeRightTab = 'translation'
                this.fadeShowDetail = false
                this.showTranslation = true
                this.$api.Task.translationLyc({
                    lyc: this.musicInfo.lyrics
                }).then((res) => {
                    this.showTranslation = true
                    this.translationText = res.data
                })
            },
            // 文件目录
            handleSearchFile() {
                this.tablePage = 1
                this.fetchFolderMusicList()
            },
            // 过滤搜索
            handleSearch() {
                this.$refs.tree1.searchNode(this.searchWord)
                const searchResult = this.$refs.tree1.getSearchResult()
                this.isEmpty = searchResult.isEmpty
                this.tablePage = 1
                this.fetchFolderMusicList()
            },
            // 保存音乐信息
            handleClick() {
                const fullPath = this.filePath + '/' + this.fileName
                const st = (fullPath && this.batchStatusMap[fullPath]) || this.batchStatusMap[this.fileName]
                if (st && (st.state === 'running' || st.state === 'wait')) {
                    this.$cwMessage('该歌曲当前正在后台处理或排队中，请等待处理完成后再保存！', 'warning')
                    return
                }
                const params = [{
                    'file_full_path': fullPath,
                    ...this.musicInfo
                }]
                this.isLoading = true
                this.$api.Task.updateId3({'music_id3_info': params}).then((res) => {
                    this.isLoading = false
                    if (res.result) {
                        this.$cwMessage('修改成功', 'success')
                        this.$store.commit('setHasMsg', true)
                        this.fetchFolderMusicList()
                    } else {
                        this.$cwMessage(res.message || '修改失败', 'error')
                    }
                }).catch((err) => {
                    this.isLoading = false
                    this.$cwMessage((err && err.message) || '修改失败', 'error')
                })
            },
            handleBatch() {
                this.$bkInfo({
                    title: '确认要批量修改？',
                    confirmLoading: true,
                    confirmFn: () => {
                        try {
                            this.isLoading = true

                            this.$api.Task.batchUpdateId3({
                                'file_full_path': this.filePath,
                                'select_data': this.checkedData,
                                'music_info': this.musicInfoManual
                            }).then((res) => {
                                this.isLoading = false
                                if (res.result) {
                                    const total = res.data ? res.data.total : 0
                                    this.$cwMessage(`批量修改任务已在后台多线程启动（共 ${total} 首），请在右上角查看进度`, 'success')
                                    this.$store.commit('setHasMsg', true)
                                } else {
                                    this.$cwMessage('提交失败: ' + (res.message || ''), 'error')
                                }
                            }).catch(() => {
                                this.isLoading = false
                            })
                            return true
                        } catch (e) {
                            this.isLoading = false
                            console.warn(e)
                            return false
                        }
                    }
                })
            },
            handleBatchAuto() {
                const selectData = this.tableSelectedRows.length > 0
                    ? this.tableSelectedRows.map(r => ({ name: r.filename, icon: 'icon-music' }))
                    : (this.checkedData && this.checkedData.length > 0 ? this.checkedData : [])
                const isApplyToAll = selectData.length === 0
                const targetRows = isApplyToAll ? this.folderMusicList : this.tableSelectedRows

                // 提交前校验待处理文件是否有任务正在执行/排队
                const activeNames = []
                for (const row of targetRows) {
                    if (!row || !row.filename) continue
                    const fullPath = row.path || (this.filePath ? this.filePath + '/' + row.filename : '')
                    const st = (fullPath && this.batchStatusMap[fullPath]) || this.batchStatusMap[row.filename]
                    if (st && (st.state === 'running' || st.state === 'wait')) {
                        activeNames.push(row.filename)
                    }
                }
                if (activeNames.length > 0) {
                    const sample = activeNames.slice(0, 3).join('、')
                    const extra = activeNames.length > 3 ? ` 等共 ${activeNames.length} 首` : ''
                    this.$cwMessage(`检测到有歌曲（${sample}${extra}）正在处理或排队中，请等待当前任务全部执行完毕后再提交！`, 'warning')
                    return
                }

                this.$bkInfo({
                    title: '确认要自动批量修改？',
                    confirmLoading: false,
                    confirmFn: () => {
                        this.exampleSetting1.primary.visible = false
                        targetRows.forEach(row => {
                            if (row && row.filename) {
                                this.$set(this.batchStatusMap, row.filename, { state: 'wait', extra: '' })
                            }
                        })
                        this.$cwMessage('自动匹配修改任务已提交，后台正在处理中...', 'primary')

                        this.musicInfoManual['select_mode'] = this.selectAutoMode
                        this.musicInfoManual['source_list'] = this.sourceList
                        this.$api.Task.batchAutoUpdateId3({
                            'file_full_path': this.filePath,
                            'select_data': selectData,
                            'music_info': this.musicInfoManual
                        }).then((res) => {
                            if (res.result) {
                                const batchId = res.data ? res.data.batch : ''
                                this.startBatchStatusPolling(batchId)
                            } else {
                                this.$cwMessage('提交失败: ' + (res.message || ''), 'error')
                                targetRows.forEach(row => {
                                    if (row && row.filename) {
                                        this.$delete(this.batchStatusMap, row.filename)
                                    }
                                })
                            }
                        }).catch(() => {
                            this.$cwMessage('自动匹配任务提交异常', 'error')
                            targetRows.forEach(row => {
                                if (row && row.filename) {
                                    this.$delete(this.batchStatusMap, row.filename)
                                }
                            })
                        })
                        return true
                    }
                })
            },
            openTidyModal() {
                if (!this.filePath) {
                    this.$cwMessage('请先在左侧选择一个文件夹', 'warning')
                    return
                }
                this.tidyScope = 'all'
                if (!this.tidyFormData.root_path) {
                    this.tidyFormData.root_path = '/app/media/'
                }
                this.exampleSetting2.primary.visible = true
            },
            handleTidy() {
                const isApplyToAll = this.tidyScope === 'all'
                const targetRows = isApplyToAll ? this.folderMusicList : this.tableSelectedRows
                const targetCount = isApplyToAll ? this.folderMusicTotal : this.tableSelectedRows.length

                if (targetCount === 0) {
                    this.$cwMessage('当前没有待整理的歌曲', 'warning')
                    return
                }

                // 提交前校验待处理文件是否有任务正在执行/排队
                const activeNames = []
                for (const row of targetRows) {
                    if (!row || !row.filename) continue
                    const fullPath = row.path || (this.filePath ? this.filePath + '/' + row.filename : '')
                    const st = (fullPath && this.batchStatusMap[fullPath]) || this.batchStatusMap[row.filename]
                    if (st && (st.state === 'running' || st.state === 'wait')) {
                        activeNames.push(row.filename)
                    }
                }
                if (activeNames.length > 0) {
                    const sample = activeNames.slice(0, 3).join('、')
                    const extra = activeNames.length > 3 ? ` 等共 ${activeNames.length} 首` : ''
                    this.$cwMessage(`检测到有歌曲（${sample}${extra}）正在处理或排队中，请等待当前任务全部执行完毕后再提交！`, 'warning')
                    return
                }

                const firstOpt = this.tidyList.find(o => o.id === this.tidyFormData.first_dir)
                const secondOpt = this.tidyFormData.second_dir ? this.tidyList.find(o => o.id === this.tidyFormData.second_dir) : null
                const ruleDesc = `一级【${firstOpt ? firstOpt.name : this.tidyFormData.first_dir}】` + (secondOpt ? `、二级【${secondOpt.name}】` : '')

                this.$bkInfo({
                    title: `确认要整理分类文件夹（共 ${targetCount} 首）？`,
                    subTitle: `将按${ruleDesc}归档至目录：${this.tidyFormData.root_path}`,
                    confirmLoading: false,
                    confirmFn: () => {
                        this.exampleSetting2.primary.visible = false

                        // 将受影响行立即标为 wait (待整理)
                        targetRows.forEach(row => {
                            if (row && row.filename) {
                                this.$set(this.batchStatusMap, row.filename, { state: 'wait', extra: '' })
                            }
                        })
                        this.$cwMessage(`整理分类任务已提交（共 ${targetCount} 首），正在后台处理中...`, 'primary')

                        const payload = {
                            root_path: this.tidyFormData.root_path || '/app/media/',
                            first_dir: this.tidyFormData.first_dir || 'artist',
                            second_dir: this.tidyFormData.second_dir || '',
                            file_full_path: this.filePath,
                            apply_to_all: isApplyToAll,
                            select_data: isApplyToAll ? [] : this.tableSelectedRows.map(r => ({
                                name: r.filename,
                                filename: r.filename,
                                path: r.path,
                                artist: r.artist
                            })),
                            move_lrc: this.tidyFormData.move_lrc !== false,
                            conflict_action: this.tidyFormData.conflict_action || 'skip',
                            clean_empty_dir: Boolean(this.tidyFormData.clean_empty_dir)
                        }

                        this.$api.Task.tidyFolder(payload).then((res) => {
                            if (res.result) {
                                const batchId = res.data ? res.data.batch : ''
                                this.startBatchStatusPolling(batchId)
                                this.$store.commit('setHasMsg', true)
                            } else {
                                this.$cwMessage('提交整理失败: ' + (res.message || ''), 'error')
                                targetRows.forEach(row => {
                                    if (row && row.filename) {
                                        this.$delete(this.batchStatusMap, row.filename)
                                    }
                                })
                            }
                        }).catch((err) => {
                            this.$cwMessage('整理任务提交异常: ' + err, 'error')
                            targetRows.forEach(row => {
                                if (row && row.filename) {
                                    this.$delete(this.batchStatusMap, row.filename)
                                }
                            })
                        })
                        return true
                    }
                })
            },
            changeSorted(element) {
                if (this.sortedField.includes(element)) {
                    this.sortedField.splice(this.sortedField.indexOf(element), 1)
                } else {
                    this.sortedField.push(element)
                }
                const obj = JSON.stringify(this.sortedField)
                window.localStorage.setItem('sortedField', obj)
                this.handleSearchFile()
            },
            handleSettings() {
                const obj = JSON.stringify(this.showFields)
                window.localStorage.setItem('showFields', obj)
                window.localStorage.setItem('resource', this.resource)
            },
            handleRes(response) {
                if (response.result) {
                    let dataUrl = response.data
                    if (dataUrl && !dataUrl.startsWith('data:image/')) {
                        dataUrl = 'data:image/jpeg;base64,' + dataUrl
                    }
                    this.musicInfo.album_img = dataUrl
                    return true
                } else {
                    return false
                }
            },
            handleResBatch(response) {
                if (response.result) {
                    let dataUrl = response.data
                    if (dataUrl && !dataUrl.startsWith('data:image/')) {
                        dataUrl = 'data:image/jpeg;base64,' + dataUrl
                    }
                    this.musicInfoManual.album_img = dataUrl
                    return true
                } else {
                    return false
                }
            },
            // 表头与多属性批量修改相关方法
            renderHeaderWithBatch(h, { column }, field, label) {
                return h('div', {
                    class: 'custom-table-header-cell',
                    style: {
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: column.align === 'center' ? 'center' : 'flex-start',
                        width: '100%'
                    }
                }, [
                    h('span', label),
                    h('i', {
                        class: 'bk-icon icon-edit header-batch-icon',
                        attrs: {
                            title: `批量修改【${label}】`
                        },
                        on: {
                            click: (e) => {
                                e.stopPropagation()
                                this.openMultiBatchModal(field)
                            }
                        }
                    })
                ])
            },
            handleTableSelectionChange(selection) {
                this.tableSelectedRows = selection
            },
            clearTableSelection() {
                if (this.$refs.musicTable) {
                    this.$refs.musicTable.clearSelection()
                }
                this.tableSelectedRows = []
            },
            getFileStatus(row) {
                if (!row || !row.filename) return 'none'
                const fullPath = row.path || (this.filePath ? this.filePath + '/' + row.filename : '')
                const item = (fullPath && this.batchStatusMap[fullPath]) || this.batchStatusMap[row.filename]
                if (item && item.state) {
                    return item.state
                }
                return row.state || 'none'
            },
            getFileStatusExtra(row) {
                if (!row || !row.filename) return ''
                const fullPath = row.path || (this.filePath ? this.filePath + '/' + row.filename : '')
                const item = (fullPath && this.batchStatusMap[fullPath]) || this.batchStatusMap[row.filename]
                if (item && item.extra) {
                    return item.extra
                }
                return row.extra || ''
            },
            openMultiBatchModal(field = 'title') {
                if (!this.filePath) {
                    this.$cwMessage('请先在左侧选择一个文件夹', 'warning')
                    return
                }
                if (this.tableSelectedRows.length > 0) {
                    this.batchScope = 'selected'
                } else {
                    this.batchScope = 'all'
                }
                if (field && this.batchFieldsEnabled[field] !== undefined) {
                    this.activeBatchTab = field
                    this.batchFieldsEnabled[field] = true
                }
                this.batchModalVisible = true
            },
            closeMultiBatchModal() {
                this.batchModalVisible = false
            },
            insertVariableTag(tag) {
                const cfg = this.batchConfig[this.activeBatchTab]
                if (cfg) {
                    cfg.template = (cfg.template || '') + tag
                }
            },
            applyPreset(presetKey) {
                const f = this.activeBatchTab
                const cfg = this.batchConfig[f]
                if (!cfg) return

                if (f === 'title') {
                    if (presetKey === 'clean_number_prefix') {
                        cfg.template = '${filename_no_ext}'
                        cfg.trim_start = 0
                        cfg.trim_end = 0
                        cfg.replace_search = ''
                        cfg.replace_with = ''
                        cfg.regex_search = '^\\d+[-_\\s|.]+ ?'
                        cfg.regex_replace = ''
                        cfg.strip = true
                    } else if (presetKey === 'filename_no_ext') {
                        cfg.template = '${filename_no_ext}'
                        cfg.trim_start = 0
                        cfg.trim_end = 0
                        cfg.replace_search = ''
                        cfg.replace_with = ''
                        cfg.regex_search = ''
                        cfg.regex_replace = ''
                        cfg.strip = true
                    } else if (presetKey === 'artist_title') {
                        cfg.template = '${artist} - ${title}'
                    } else if (presetKey === 'remove_brackets') {
                        cfg.regex_search = '\\s*[\\(\\[【（].*?[\\)\\]】）]'
                        cfg.regex_replace = ''
                    } else if (presetKey === 'underscore_to_space') {
                        cfg.replace_search = '_'
                        cfg.replace_with = ' '
                    }
                } else if (f === 'tracknumber') {
                    if (presetKey === 'track_from_filename_prefix') {
                        cfg.mode = 'extract_filename'
                        cfg.template = '${filename_no_ext}'
                        cfg.regex_search = '^(\\d+)'
                        cfg.regex_replace = '$1'
                        cfg.trim_start = 0
                        cfg.trim_end = 0
                        cfg.replace_search = ''
                        cfg.replace_with = ''
                        cfg.strip = true
                    } else if (presetKey === 'track_from_multidisc') {
                        cfg.mode = 'extract_multidisc'
                        cfg.template = '${filename_no_ext}'
                        cfg.regex_search = '^(?:CD)?(\\d+)[-_.](\\d+)'
                        cfg.regex_replace = '$2'
                        cfg.trim_start = 0
                        cfg.trim_end = 0
                        cfg.replace_search = ''
                        cfg.replace_with = ''
                        cfg.strip = true
                        // 联动开启光盘编号并配置抽取第1组
                        this.batchFieldsEnabled.discnumber = true
                        this.batchConfig.discnumber.mode = 'extract_filename'
                        this.batchConfig.discnumber.template = '${filename_no_ext}'
                        this.batchConfig.discnumber.regex_search = '^(?:CD)?(\\d+)[-_.]\\d+'
                        this.batchConfig.discnumber.regex_replace = '$1'
                        this.$cwMessage('已自动联动启用【光盘编号】，将同时抽取前置碟号', 'primary')
                    } else if (presetKey === 'track_from_word') {
                        cfg.mode = 'extract_word'
                        cfg.template = '${filename_no_ext}'
                        cfg.regex_search = '(?:Track|第)\\s*(\\d+)'
                        cfg.regex_replace = '$1'
                        cfg.trim_start = 0
                        cfg.trim_end = 0
                        cfg.replace_search = ''
                        cfg.replace_with = ''
                        cfg.strip = true
                    } else if (presetKey === 'track_sequence') {
                        cfg.mode = 'sequence'
                        cfg.seq_start = 1
                    }
                } else if (f === 'discnumber') {
                    if (presetKey === 'disc_fixed_1') {
                        cfg.mode = 'fixed'
                        cfg.fixed_value = 1
                    } else if (presetKey === 'disc_fixed_2') {
                        cfg.mode = 'fixed'
                        cfg.fixed_value = 2
                    } else if (presetKey === 'disc_from_filename_prefix') {
                        cfg.mode = 'extract_filename'
                        cfg.template = '${filename_no_ext}'
                        cfg.regex_search = '^(?:CD)?(\\d+)[-_.]\\d+'
                        cfg.regex_replace = '$1'
                    } else if (presetKey === 'disc_from_folder') {
                        cfg.mode = 'extract_folder'
                        cfg.template = '${parent_folder}'
                        cfg.regex_search = '(?:CD|Disc|碟)?\\s*(\\d+)'
                        cfg.regex_replace = '$1'
                    }
                } else if (f === 'filename') {
                    if (presetKey === 'artist_title') {
                        cfg.template = '${artist} - ${title}'
                    } else if (presetKey === 'track_title') {
                        cfg.template = '${tracknumber}.${title}'
                    } else if (presetKey === 'underscore_to_space') {
                        cfg.replace_search = '_'
                        cfg.replace_with = ' '
                    }
                } else if (f === 'artist') {
                    if (presetKey === 'from_albumartist') {
                        cfg.template = '${albumartist}'
                    } else if (presetKey === 'underscore_to_space') {
                        cfg.replace_search = '_'
                        cfg.replace_with = ' '
                    }
                } else if (f === 'album') {
                    if (presetKey === 'from_title') {
                        cfg.template = '${title}'
                    } else if (presetKey === 'from_filename') {
                        cfg.template = '${filename_no_ext}'
                    } else if (presetKey === 'from_folder') {
                        cfg.template = '${folder}'
                    }
                } else if (f === 'albumartist') {
                    if (presetKey === 'from_artist') {
                        cfg.template = '${artist}'
                    }
                }
            },
            handleBatchCoverUploadRes(response) {
                if (response.result && response.data) {
                    let dataUrl = response.data
                    if (!dataUrl.startsWith('data:image/')) {
                        dataUrl = 'data:image/jpeg;base64,' + dataUrl
                    }
                    this.batchConfig.album_img.img_base64 = dataUrl
                    this.batchConfig.album_img.preview_url = dataUrl
                    this.batchConfig.album_img.clear_cover = false
                    this.batchFieldsEnabled.album_img = true
                    this.batchCoverFiles = [{
                        name: 'cover.jpg',
                        status: 'done',
                        url: dataUrl
                    }]
                    this.$cwMessage('封面图片上传成功', 'success')
                    return true
                } else {
                    this.$cwMessage('图片上传失败', 'error')
                    return false
                }
            },
            removeBatchCover() {
                this.batchConfig.album_img.img_base64 = ''
                this.batchConfig.album_img.preview_url = ''
                this.batchCoverFiles = []
                this.batchReloadImg = false
                this.$nextTick(() => {
                    this.batchReloadImg = true
                })
            },
            handleClearCoverChange(val) {
                if (val) {
                    this.batchConfig.album_img.img_base64 = ''
                    this.batchConfig.album_img.preview_url = ''
                    this.batchCoverFiles = []
                    this.batchReloadImg = false
                    this.$nextTick(() => {
                        this.batchReloadImg = true
                    })
                }
            },
            formatNumberPadding(numStr, padding) {
                if (!numStr) return ''
                const m = String(numStr).match(/\d+/)
                if (!m) return numStr
                const num = parseInt(m[0], 10)
                if (isNaN(num)) return numStr
                if (padding === 'pad2') {
                    return String(num).padStart(2, '0')
                } else if (padding === 'pad3') {
                    return String(num).padStart(3, '0')
                } else if (padding === 'raw') {
                    return String(num)
                }
                return numStr
            },
            evaluateFieldPreview(song, fieldName, songIndex = 0) {
                if (!song) return ''
                if (fieldName === 'album_img') return ''
                const config = this.batchConfig[fieldName]
                if (!config) return song[fieldName] || ''

                // 专有逻辑：音轨号自增模式
                if (fieldName === 'tracknumber' && config.mode === 'sequence') {
                    const start = Number(config.seq_start) || 1
                    const seqNum = start + songIndex
                    return this.formatNumberPadding(String(seqNum), config.padding)
                }

                // 专有逻辑：光盘编号固定值
                if (fieldName === 'discnumber' && config.mode === 'fixed') {
                    return String(config.fixed_value || 1)
                }

                const filename = song.filename || ''
                const extMatch = filename.lastIndexOf('.')
                const filenameNoExt = extMatch !== -1 ? filename.substring(0, extMatch) : filename
                const ext = extMatch !== -1 ? filename.substring(extMatch + 1) : ''
                const parentFolder = (song.path ? song.path.split('/').filter(Boolean).slice(-2, -1)[0] : '') || (this.filePath ? this.filePath.split('/').filter(Boolean).pop() : '') || ''

                const varDict = {
                    filename: filename,
                    filename_no_ext: filenameNoExt,
                    basename: filenameNoExt,
                    folder: parentFolder,
                    parent_folder: parentFolder,
                    dirname: parentFolder,
                    folder_name: parentFolder,
                    title: song.title || '',
                    artist: song.artist || '',
                    album: song.album || '',
                    albumartist: song.albumartist || '',
                    tracknumber: song.tracknumber || '',
                    discnumber: song.discnumber || '',
                    year: song.year || '',
                    genre: song.genre || ''
                }

                let val = config.template || ''
                val = val.replace(/\$\{(.*?)\}/g, (match, p1) => {
                    const k = p1.trim()
                    return varDict[k] !== undefined ? varDict[k] : match
                })

                const trimStart = Number(config.trim_start) || 0
                const trimEnd = Number(config.trim_end) || 0
                if (trimStart > 0) {
                    val = val.substring(trimStart)
                }
                if (trimEnd > 0) {
                    val = val.substring(0, Math.max(0, val.length - trimEnd))
                }

                if (config.replace_search) {
                    val = val.split(config.replace_search).join(config.replace_with || '')
                }

                if (config.regex_search) {
                    try {
                        const repl = config.regex_replace || ''
                        if (repl === '$1' || repl === '$2' || repl === '$3') {
                            const grpIdx = parseInt(repl.substring(1), 10)
                            const m = val.match(new RegExp(config.regex_search))
                            if (m && m[grpIdx] !== undefined) {
                                val = m[grpIdx]
                            }
                        } else {
                            val = val.replace(new RegExp(config.regex_search, 'g'), repl)
                        }
                    } catch (e) {
                        // ignore regex pattern error during live typing
                    }
                }

                if (config.strip) {
                    val = val.trim()
                }

                if (fieldName === 'tracknumber' || fieldName === 'discnumber') {
                    val = this.formatNumberPadding(val, config.padding)
                }

                if (fieldName === 'filename' && ext) {
                    if (!val.endsWith('.' + ext)) {
                        val = val + '.' + ext
                    }
                }

                return val
            },
            handleConfirmMultiBatch() {
                if (!this.hasAnyFieldEnabled) {
                    this.$cwMessage('请至少勾选启用一个需要修改的属性', 'warning')
                    return
                }

                const musicInfo = {
                    transform_rules: {}
                }

                if (this.batchFieldsEnabled.album_img) {
                    if (this.batchConfig.album_img.clear_cover) {
                        musicInfo.clear_cover = true
                    } else if (this.batchConfig.album_img.img_base64) {
                        musicInfo.album_img = this.batchConfig.album_img.img_base64
                    }
                    musicInfo.is_save_album_cover = this.batchConfig.album_img.is_save_album_cover
                }

                const textFields = ['filename', 'title', 'artist', 'album', 'albumartist', 'year', 'genre', 'tracknumber', 'discnumber']
                for (const f of textFields) {
                    if (this.batchFieldsEnabled[f]) {
                        if (f === 'discnumber' && this.batchConfig.discnumber.mode === 'fixed') {
                            musicInfo.discnumber = String(this.batchConfig.discnumber.fixed_value || 1)
                        } else if (f === 'tracknumber' && this.batchConfig.tracknumber.mode === 'sequence') {
                            musicInfo.tracknumber = '${sequence_index}'
                            musicInfo.transform_rules.tracknumber = {
                                padding: this.batchConfig.tracknumber.padding
                            }
                        } else {
                            musicInfo[f] = this.batchConfig[f].template
                            musicInfo.transform_rules[f] = {
                                trim_start: this.batchConfig[f].trim_start,
                                trim_end: this.batchConfig[f].trim_end,
                                replace_search: this.batchConfig[f].replace_search,
                                replace_with: this.batchConfig[f].replace_with,
                                regex_search: this.batchConfig[f].regex_search,
                                regex_replace: this.batchConfig[f].regex_replace,
                                strip: this.batchConfig[f].strip,
                                padding: this.batchConfig[f].padding
                            }
                        }
                    }
                }

                const isApplyToAll = this.batchScope === 'all'
                const targetRows = isApplyToAll ? this.folderMusicList : this.tableSelectedRows
                const targetSongsCount = this.targetSongsCount

                const isTrackSequence = this.batchFieldsEnabled.tracknumber && this.batchConfig.tracknumber.mode === 'sequence'
                const isDiscFixed = this.batchFieldsEnabled.discnumber && this.batchConfig.discnumber.mode === 'fixed'

                const selectData = targetRows.map((r, idx) => {
                    const itemData = {
                        name: r.filename,
                        icon: 'icon-music',
                        sequence_index: idx + (Number(this.batchConfig.tracknumber.seq_start) || 1)
                    }
                    if (this.batchFieldsEnabled.tracknumber) {
                        itemData.tracknumber = this.evaluateFieldPreview(r, 'tracknumber', idx)
                    }
                    if (this.batchFieldsEnabled.discnumber) {
                        itemData.discnumber = isDiscFixed ? String(this.batchConfig.discnumber.fixed_value || 1) : this.evaluateFieldPreview(r, 'discnumber', idx)
                    }
                    return itemData
                })

                // 提交前校验待处理文件是否有任务正在执行/排队
                const activeNames = []
                for (const row of targetRows) {
                    if (!row || !row.filename) continue
                    const fullPath = row.path || (this.filePath ? this.filePath + '/' + row.filename : '')
                    const st = (fullPath && this.batchStatusMap[fullPath]) || this.batchStatusMap[row.filename]
                    if (st && (st.state === 'running' || st.state === 'wait')) {
                        activeNames.push(row.filename)
                    }
                }
                if (activeNames.length > 0) {
                    const sample = activeNames.slice(0, 3).join('、')
                    const extra = activeNames.length > 3 ? ` 等共 ${activeNames.length} 首` : ''
                    this.$cwMessage(`检测到有歌曲（${sample}${extra}）正在处理或排队中，请等待当前任务全部执行完毕后再提交！`, 'warning')
                    this.isBatchSubmitting = false
                    return
                }

                // 立即关闭批量修改弹窗，立刻回到文件列表页面，不阻塞用户操作
                this.batchModalVisible = false
                this.isBatchSubmitting = false

                // 将受影响行立即标为 wait (待修改)
                targetRows.forEach(row => {
                    if (row && row.filename) {
                        this.$set(this.batchStatusMap, row.filename, { state: 'wait', extra: '' })
                    }
                })

                this.$cwMessage('批量修改任务已提交（共 ' + targetSongsCount + ' 首），正在后台处理中...', 'primary')

                this.$api.Task.batchUpdateId3({
                    file_full_path: this.filePath,
                    select_data: selectData,
                    apply_to_all: isApplyToAll && !isTrackSequence,
                    music_info: musicInfo
                }).then((res) => {
                    if (res.result) {
                        const batchId = res.data ? res.data.batch : ''
                        this.startBatchStatusPolling(batchId)
                    } else {
                        this.$cwMessage('批量修改提交失败: ' + (res.message || ''), 'error')
                        targetRows.forEach(row => {
                            if (row && row.filename) {
                                this.$delete(this.batchStatusMap, row.filename)
                            }
                        })
                    }
                }).catch(() => {
                    this.$cwMessage('批量修改请求异常', 'error')
                    targetRows.forEach(row => {
                        if (row && row.filename) {
                            this.$delete(this.batchStatusMap, row.filename)
                        }
                    })
                })
            },
            initEventSource() {
                if (typeof EventSource === 'undefined') {
                    return
                }
                if (this.sseSource) {
                    try {
                        this.sseSource.close()
                    } catch (e) {}
                }
                this.sseSource = new EventSource('/api/events/')

                this.sseSource.addEventListener('task_item', (event) => {
                    try {
                        const data = JSON.parse(event.data)
                        this.handleSseTaskItem(data)
                    } catch (e) {}
                })

                this.sseSource.addEventListener('task_batch', (event) => {
                    try {
                        const data = JSON.parse(event.data)
                        this.handleSseTaskBatch(data)
                    } catch (e) {}
                })

                this.sseSource.onerror = (e) => {
                    // 原生 EventSource 会自动按 interval 尝试重连
                }
            },
            closeEventSource() {
                if (this.sseSource) {
                    try {
                        this.sseSource.close()
                    } catch (e) {}
                    this.sseSource = null
                }
            },
            handleSseTaskItem(data) {
                if (!data) return
                const fn = data.filename
                const fp = data.full_path
                const state = data.state
                const extra = data.extra || ''
                const meta = data.meta

                this.$set(this.batchStatusMap, fn, { state, extra })
                if (fp) {
                    this.$set(this.batchStatusMap, fp, { state, extra })
                }

                // 局部更新列表当前行状态、封面与全部元数据字段，实时更新行数据！
                const row = this.folderMusicList.find(r => r.filename === fn || (fp && r.path === fp))
                if (row) {
                    this.$set(row, 'state', state)
                    this.$set(row, 'extra', extra)
                    if (state === 'success') {
                        this.$set(row, 'has_cover', true)
                        const freshCover = data.cover_url || `/api/music_cover/?file_path=${encodeURIComponent(data.parent_path || this.filePath)}&file_name=${encodeURIComponent(fn)}&t=${Date.now()}`
                        this.$set(row, 'cover_url', freshCover)

                        // 实时同步更新其他全部元数据字段，避免仅封面刷新
                        if (meta) {
                            if (meta.title !== undefined) this.$set(row, 'title', meta.title)
                            if (meta.artist !== undefined) this.$set(row, 'artist', meta.artist)
                            if (meta.album !== undefined) this.$set(row, 'album', meta.album)
                            if (meta.albumartist !== undefined) this.$set(row, 'albumartist', meta.albumartist)
                            if (meta.year !== undefined) this.$set(row, 'year', meta.year)
                            if (meta.genre !== undefined) this.$set(row, 'genre', meta.genre)
                            if (meta.has_lyrics !== undefined) this.$set(row, 'has_lyrics', meta.has_lyrics)
                            if (meta.has_cover !== undefined) this.$set(row, 'has_cover', meta.has_cover)
                            if (meta.filename && meta.filename !== row.filename) {
                                this.$set(row, 'filename', meta.filename)
                            }
                            if (meta.path) {
                                this.$set(row, 'path', meta.path)
                            }
                        }
                    }
                }

                // 若右侧编辑抽屉正展开该歌曲，实时更新封面与各字段
                if (this.fileName === fn && state === 'success') {
                    this.musicInfo.album_img = `/api/music_cover/?file_path=${encodeURIComponent(this.filePath)}&file_name=${encodeURIComponent(fn)}&t=${Date.now()}`
                    if (meta) {
                        if (meta.title !== undefined) this.musicInfo.title = meta.title
                        if (meta.artist !== undefined) this.musicInfo.artist = meta.artist
                        if (meta.album !== undefined) this.musicInfo.album = meta.album
                        if (meta.albumartist !== undefined) this.musicInfo.albumartist = meta.albumartist
                        if (meta.year !== undefined) this.musicInfo.year = meta.year
                        if (meta.genre !== undefined) this.musicInfo.genre = meta.genre
                    }
                }

                // 若任务监控弹窗打开中，实时更新对应条目状态
                if (this.taskRecords && this.taskRecords.length > 0) {
                    const rec = this.taskRecords.find(r => (fp && r.full_path === fp) || r.filename === fn)
                    if (rec) {
                        this.$set(rec, 'state', state)
                        this.$set(rec, 'extra', extra)
                        if (meta && meta.title) {
                            this.$set(rec, 'song_name', meta.title)
                        }
                        if (meta && meta.artist) {
                            this.$set(rec, 'artist', meta.artist)
                        }
                    }
                }
            },
            handleSseTaskBatch(data) {
                if (!data) return
                if (this.taskStats) {
                    this.taskStats.total = data.total !== undefined ? data.total : this.taskStats.total
                    this.taskStats.running = Math.max(0, (data.total || 0) - (data.finished || 0))
                    this.taskStats.wait = 0
                    this.taskStats.success = data.success !== undefined ? data.success : this.taskStats.success
                    this.taskStats.failed = data.failed !== undefined ? data.failed : this.taskStats.failed
                }

                // 若任务监控弹窗打开中，静默刷新当前页
                if (this.taskDrawerVisible) {
                    this.loadTaskRecords(this.taskCurrentPage, false)
                }

                if (data.is_done) {
                    if (this.batchPollTimer) {
                        clearInterval(this.batchPollTimer)
                        this.batchPollTimer = null
                    }
                    this.fetchTaskStats()
                    this.cacheBuster = Date.now()
                    this.fetchFolderMusicList()
                    if (data.batch_id === this.currentBatchId) {
                        this.isBatchSubmitting = false
                        if (data.failed > 0) {
                            this.$cwMessage(`批量处理完成：成功 ${data.success} 首，失败 ${data.failed} 首（可点击右上角「任务列表」查看详情）`, 'warning')
                        } else {
                            this.$cwMessage(`批量处理已全部完成（共 ${data.total} 首，全部成功）`, 'success')
                        }
                    }
                }
            },
            startBatchStatusPolling(batchId) {
                if (!batchId) return
                this.currentBatchId = batchId
                if (this.batchPollTimer) {
                    clearInterval(this.batchPollTimer)
                    this.batchPollTimer = null
                }
                const poll = () => {
                    this.$api.Task.batchProgress({
                        batch: this.currentBatchId,
                        include_records: true
                    }).then(pres => {
                        if (pres.result && pres.data) {
                            const records = pres.data.records || {}
                            for (const fn in records) {
                                this.$set(this.batchStatusMap, fn, records[fn])
                                const row = this.folderMusicList.find(r => r.filename === fn)
                                if (row) {
                                    this.$set(row, 'state', records[fn].state)
                                    this.$set(row, 'extra', records[fn].extra)
                                }
                            }
                            if (this.taskStats) {
                                this.taskStats.total = pres.data.total !== undefined ? pres.data.total : this.taskStats.total
                                this.taskStats.running = Math.max(0, (pres.data.total || 0) - (pres.data.finished || 0))
                                this.taskStats.wait = 0
                                this.taskStats.success = pres.data.success !== undefined ? pres.data.success : this.taskStats.success
                                this.taskStats.failed = pres.data.failed !== undefined ? pres.data.failed : this.taskStats.failed
                            }
                            if (this.taskDrawerVisible) {
                                this.loadTaskRecords(this.taskCurrentPage, false)
                            }
                            if (pres.data.is_done) {
                                if (this.batchPollTimer) {
                                    clearInterval(this.batchPollTimer)
                                    this.batchPollTimer = null
                                }
                                this.cacheBuster = Date.now()
                                if (pres.data.failed > 0) {
                                    this.$cwMessage(`批量修改完成：成功 ${pres.data.success} 首，失败 ${pres.data.failed} 首（可点击右上角「任务列表」查看失败原因与详情）`, 'warning')
                                } else {
                                    this.$cwMessage(`批量修改已全部完成（共 ${pres.data.total} 首，全部成功）`, 'success')
                                }
                                this.fetchTaskStats()
                                this.fetchFolderMusicList()
                                if (this.fileName) {
                                    this.loadSongDetail(this.fileName)
                                }
                            }
                        }
                    }).catch(() => {
                        if (this.batchPollTimer) {
                            clearInterval(this.batchPollTimer)
                            this.batchPollTimer = null
                        }
                    })
                }
                // 轮询兜底（优先由 SSE 实时推送毫秒级生效）
                this.batchPollTimer = setInterval(poll, 1500)
            },
            handleForceRefreshCache() {
                this.isForceRefreshing = true
                this.$api.Task.forceRefreshCache({ file_path: this.filePath }).then(res => {
                    this.cacheBuster = Date.now()
                    this.fetchTaskStats()
                    this.fetchFolderMusicList()
                    this.$cwMessage('缓存已全部强制清空，已重新读取最新磁盘数据与封面', 'success')
                }).catch(err => {
                    this.$cwMessage('强制刷新缓存失败: ' + err, 'error')
                }).finally(() => {
                    this.isForceRefreshing = false
                })
            },
            openTaskDrawer() {
                this.taskDrawerVisible = true
                this.fetchTaskStats()
                this.loadTaskRecords(1, true)
                this.startTaskDrawerAutoRefresh()
            },
            startTaskDrawerAutoRefresh() {
                this.stopTaskDrawerAutoRefresh()
                this.taskDrawerTimer = setInterval(() => {
                    if (this.taskDrawerVisible && (this.taskStats.running > 0 || this.isBatchSubmitting)) {
                        this.fetchTaskStats()
                        if (!this.isTaskLoading) {
                            this.loadTaskRecords(this.taskCurrentPage, false)
                        }
                    } else if (this.taskStats.running === 0 && !this.isBatchSubmitting) {
                        this.stopTaskDrawerAutoRefresh()
                    }
                }, 1500)
            },
            stopTaskDrawerAutoRefresh() {
                if (this.taskDrawerTimer) {
                    clearInterval(this.taskDrawerTimer)
                    this.taskDrawerTimer = null
                }
            },
            fetchTaskStats() {
                this.$api.Task.getRecordStats().then(res => {
                    if (res.result && res.data) {
                        this.taskStats = Object.assign({}, this.taskStats, res.data)
                    }
                }).catch(() => {})
            },
            loadTaskRecords(page = 1, showLoading = true) {
                if (showLoading) {
                    this.isTaskLoading = true
                }
                this.taskCurrentPage = page
                const params = {
                    page: page,
                    page_size: this.taskPageSize
                }
                if (this.taskFilterState) {
                    params.state = this.taskFilterState
                }
                if (this.taskFilterBatch) {
                    params.batch = this.taskFilterBatch
                }
                if (this.taskSearchWord) {
                    params.search = this.taskSearchWord
                }
                this.$api.Task.getRecord(params).then(res => {
                    if (res.result && res.data) {
                        this.taskRecords = res.data.items || []
                        this.taskTotalCount = res.data.count || 0
                    }
                }).catch(err => {
                    if (showLoading) {
                        this.$cwMessage('加载任务记录失败: ' + err, 'error')
                    }
                }).finally(() => {
                    this.isTaskLoading = false
                })
            },
            filterTaskByState(state) {
                this.taskFilterState = state
                this.loadTaskRecords(1)
            },
            handleTaskFilterChange() {
                this.loadTaskRecords(1)
            },
            handleTaskPageChange(page) {
                this.loadTaskRecords(page)
            },
            handleTaskLimitChange(limit) {
                this.taskPageSize = limit
                this.loadTaskRecords(1)
            },
            handleResumePending() {
                this.$api.Task.resumePending({ batch: this.taskFilterBatch }).then(res => {
                    if (res.result) {
                        this.$cwMessage(`已成功继续执行 ${res.data ? res.data.total : 0} 个排队任务`, 'success')
                        this.fetchTaskStats()
                        this.loadTaskRecords(this.taskCurrentPage, false)
                        if (res.data && res.data.batch) {
                            this.startBatchStatusPolling(res.data.batch)
                        }
                    } else {
                        this.$cwMessage('继续任务失败: ' + (res.message || ''), 'error')
                    }
                }).catch(err => {
                    this.$cwMessage('继续任务请求异常: ' + err, 'error')
                })
            },
            handleRetryAllFailed() {
                this.$api.Task.retryFailed({ batch: this.taskFilterBatch }).then(res => {
                    if (res.result) {
                        this.$cwMessage(`已重新提交 ${res.data ? res.data.total : 0} 个失败任务`, 'success')
                        this.fetchTaskStats()
                        this.loadTaskRecords(1)
                    } else {
                        this.$cwMessage('重试失败: ' + (res.message || ''), 'error')
                    }
                }).catch(err => {
                    this.$cwMessage('重试请求出错: ' + err, 'error')
                })
            },
            handleRetrySingle(row) {
                this.$api.Task.retrySingleRecord({ id: row.id }).then(res => {
                    if (res.result) {
                        this.$cwMessage(`任务【${row.filename || row.song_name}】已重新加入执行队列`, 'success')
                        this.fetchTaskStats()
                        this.loadTaskRecords(this.taskCurrentPage)
                    } else {
                        this.$cwMessage('重试失败: ' + (res.message || ''), 'error')
                    }
                }).catch(err => {
                    this.$cwMessage('重试请求出错: ' + err, 'error')
                })
            },
            handleClearTasks() {
                this.$bkInfo({
                    title: '确认清空任务执行记录？',
                    subTitle: '清空后历史执行记录将无法找回，已完成的音乐标签文件不受影响。',
                    confirmFn: () => {
                        this.$api.Task.clearRecord({
                            batch: this.taskFilterBatch,
                            state: this.taskFilterState
                        }).then(res => {
                            this.$cwMessage(res.message || '任务记录已成功清空', 'success')
                            this.fetchTaskStats()
                            this.loadTaskRecords(1)
                        }).catch(err => {
                            this.$cwMessage('清空记录失败: ' + err, 'error')
                        })
                    }
                })
            },
            formatBatchTime(batchStr) {
                if (!batchStr) return ''
                try {
                    const ts = Number(batchStr)
                    if (isNaN(ts) || ts <= 0) return batchStr
                    const d = new Date(ts)
                    const pad = n => n < 10 ? '0' + n : n
                    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
                } catch (e) {
                    return batchStr
                }
            },
            // ==================== AI 智能规划 Agent 方法 ====================
            initAiAgentState() {
                // 初始化提示词模板
                try {
                    const storedTemplates = localStorage.getItem('mtw_prompt_templates')
                    if (storedTemplates) {
                        const parsed = JSON.parse(storedTemplates)
                        if (Array.isArray(parsed) && parsed.length > 0) {
                            this.promptTemplates = parsed
                        }
                    }
                } catch (e) {}

                if (!this.promptTemplates || this.promptTemplates.length === 0) {
                    this.resetPromptDefaults(false)
                }

                // 初始化 AI 模型配置
                try {
                    const storedAiConfig = localStorage.getItem('mtw_ai_config')
                    if (storedAiConfig) {
                        const parsed = JSON.parse(storedAiConfig)
                        if (parsed && typeof parsed === 'object') {
                            this.aiConfig = Object.assign({}, this.aiConfig, parsed)
                        }
                    }
                } catch (e) {}
            },
            getDefaultPromptTemplates() {
                return [
                    {
                        id: 'tpl_course_default',
                        name: '得到课程/有声书规范化',
                        mode: 'course',
                        isDefault: true,
                        isBuiltin: true,
                        systemPrompt: '你是一个专业的音频元数据规范化专家。负责整理知识付费音频与有声书，根据给定的目录名与文件名，分析出规范的标题、作者、专辑和音轨号，去除标题中的期号广告冗余，输出清洗后的标准元数据。',
                        userPrompt: '当前处理目录：{dir_name}\n请针对以下音频文件列表，规划其标准 ID3 标签。\n文件列表：\n{files}\n\n规划要求：\n1. 标题 (Title)：剥离原文件名中的前置序号（如 01、001 等）、期号（如 00发刊词- -> 发刊词-）以及广告宣传字符。\n2. 艺术家 (Artist)：提取讲师/作者姓名。\n3. 专辑 (Album)：提取课程专栏名称。\n4. 音轨号 (Track)：按原前置顺序编排2位补零数字序号（如 01, 02...，发刊词可编为 00）。\n5. 流派 (Genre)：固定为「有声书」或「知识课程」。'
                    },
                    {
                        id: 'tpl_music_default',
                        name: '流行音乐元数据规划与清洗',
                        mode: 'music',
                        isDefault: true,
                        isBuiltin: true,
                        systemPrompt: '你是一个专业的音乐元数据整理专家。负责清洗音乐文件名和标签，去除广告字眼、序号、低质特征，规划精准的歌曲名、歌手名与专辑名。',
                        userPrompt: '当前处理目录：{dir_name}\n请针对以下音乐文件列表，规划其标准歌曲信息：\n{files}\n\n规划要求：\n1. 剥离广告后缀与脏字符（如「无损下载」、「[DJ版]」等无用标记，保留正式曲名及关键备注）。\n2. 规范歌手与专辑名。'
                    }
                ]
            },
            resetPromptDefaults(showToast = true) {
                this.promptTemplates = this.getDefaultPromptTemplates()
                try {
                    localStorage.setItem('mtw_prompt_templates', JSON.stringify(this.promptTemplates))
                } catch (e) {}
                if (showToast) {
                    this.$cwMessage('已恢复所有系统预置提示词模板', 'success')
                }
                if (this.promptTemplates.length > 0) {
                    this.selectPromptToEdit(this.promptTemplates[0])
                }
            },
            openAiPlanDialog() {
                if (!this.filePath) {
                    this.$cwMessage('请先在左侧选择要规划的音乐文件夹', 'warning')
                    return
                }

                // 智能根据目录名称判断推荐模式
                const pathLower = (this.filePath || '').toLowerCase()
                let targetMode = 'course'
                if (pathLower.includes('课程') || pathLower.includes('得到') || pathLower.includes('专栏') || pathLower.includes('有声') || pathLower.includes('讲座')) {
                    targetMode = 'course'
                } else if (pathLower.includes('专辑') || pathLower.includes('单曲') || pathLower.includes('精选') || pathLower.includes('歌单')) {
                    targetMode = 'music'
                } else {
                    targetMode = this.aiPlanForm.mode || 'course'
                }

                this.aiPlanForm.mode = targetMode
                this.aiPlanForm.scope = this.tableSelectedRows.length > 0 ? 'selected' : 'all'
                this.handleAiModeChange(targetMode)
                this.aiPlanDialogVisible = true
            },
            handleAiModeChange(mode) {
                this.aiPlanForm.mode = mode
                // 查找该模式下的默认推荐模板
                let matched = this.promptTemplates.find(t => t.mode === mode && t.isDefault)
                if (!matched) {
                    matched = this.promptTemplates.find(t => t.mode === mode)
                }
                if (matched) {
                    this.aiPlanForm.templateId = matched.id
                    this.aiPlanForm.systemPrompt = matched.systemPrompt || ''
                    this.aiPlanForm.userPrompt = matched.userPrompt || ''
                }
            },
            handleAiTemplateChange(tplId) {
                const matched = this.promptTemplates.find(t => t.id === tplId)
                if (matched) {
                    this.aiPlanForm.systemPrompt = matched.systemPrompt || ''
                    this.aiPlanForm.userPrompt = matched.userPrompt || ''
                }
            },
            startAiPlan() {
                if (!this.filePath) {
                    this.$cwMessage('请先在左侧选择目标文件夹', 'warning')
                    return
                }

                this.isAiPlanning = true
                const files = this.aiPlanForm.scope === 'selected'
                    ? this.tableSelectedRows.map(r => r.filename).filter(Boolean)
                    : []

                const payload = {
                    dir_path: this.filePath,
                    mode: this.aiPlanForm.mode,
                    files: files,
                    system_prompt: this.aiPlanForm.systemPrompt || '',
                    user_prompt: this.aiPlanForm.userPrompt || '',
                    ai_config: (this.aiConfig && (this.aiConfig.model || this.aiConfig.apiKey)) ? this.aiConfig : {}
                }

                this.$api.Task.agentPlan(payload).then(res => {
                    if (res && res.result) {
                        this.aiPlanResult = res.data || {}
                        const plans = this.aiPlanResult.plan || this.aiPlanResult.plans || []
                        this.planReviewItems = plans.map(p => {
                            const orig = p.current || p.original || {}
                            const prop = p.proposed || {}
                            const fname = p.name || p.filename || prop.name || ''
                            const confVal = p.confidence === 'high' ? 0.95 : (p.confidence === 'medium' ? 0.75 : (p.confidence === 'low' ? 0.5 : (typeof p.confidence === 'number' ? p.confidence : 1.0)))
                            return {
                                filename: fname,
                                original: {
                                    title: orig.title || '',
                                    artist: orig.artist || '',
                                    album: orig.album || '',
                                    tracknumber: orig.tracknumber || ''
                                },
                                title: prop.title || orig.title || '',
                                artist: prop.artist || orig.artist || '',
                                album: prop.album || orig.album || '',
                                albumartist: prop.albumartist || prop.artist || orig.albumartist || orig.artist || '',
                                tracknumber: prop.tracknumber !== undefined ? String(prop.tracknumber) : (orig.tracknumber || ''),
                                discnumber: prop.discnumber !== undefined ? String(prop.discnumber) : (orig.discnumber || '1'),
                                genre: prop.genre || orig.genre || (this.aiPlanForm.mode === 'course' ? '有声书' : ''),
                                album_img: prop.album_img || '',
                                cleanups: p.cleanups || (p.reason ? [p.reason] : []),
                                confidence: confVal,
                                reason: p.reason || '',
                                selected: true,
                                isEdited: false
                            }
                        })
                        this.aiPlanDialogVisible = false
                        this.planReviewFilter = 'all'
                        this.planReviewSearch = ''
                        this.planReviewDialogVisible = true
                        this.$cwMessage(`智能规划完成，共生成 ${plans.length} 首歌曲方案，请复核后提交`, 'success')
                    } else {
                        this.$cwMessage('规划失败: ' + (res ? res.message : '未知错误'), 'error')
                    }
                }).catch(err => {
                    this.$cwMessage('规划请求出错: ' + err, 'error')
                }).finally(() => {
                    this.isAiPlanning = false
                })
            },
            togglePlanSelectAll(val) {
                const targetState = typeof val === 'boolean' ? val : !this.isAllPlanReviewSelected
                this.planReviewItemsFiltered.forEach(item => {
                    item.selected = targetState
                })
            },
            resetPlanItem(item) {
                if (!item || !item.original) return
                item.title = item.original.title || ''
                item.artist = item.original.artist || ''
                item.album = item.original.album || ''
                item.tracknumber = item.original.tracknumber || ''
                item.isEdited = false
                this.$cwMessage(`已还原 ${item.filename} 为原标签`, 'primary')
            },
            getConfidenceClass(conf) {
                const val = conf !== undefined ? conf : 1
                if (val >= 0.9) return 'conf-high'
                if (val >= 0.7) return 'conf-med'
                return 'conf-low'
            },
            submitAiPlanExecution() {
                const selectedItems = (this.planReviewItems || []).filter(item => item.selected)
                if (selectedItems.length === 0) {
                    this.$cwMessage('请至少勾选一首歌曲进行提交', 'warning')
                    return
                }

                // 检查是否有歌曲正在处理
                const activeNames = []
                for (const item of selectedItems) {
                    const st = this.batchStatusMap[item.filename]
                    if (st && (st.state === 'running' || st.state === 'wait')) {
                        activeNames.push(item.filename)
                    }
                }
                if (activeNames.length > 0) {
                    const sample = activeNames.slice(0, 3).join('、')
                    const extra = activeNames.length > 3 ? ` 等共 ${activeNames.length} 首` : ''
                    this.$cwMessage(`检测到歌曲（${sample}${extra}）正在后台任务队列中，请等待其完成后再提交！`, 'warning')
                    return
                }

                const selectData = selectedItems.map(item => ({
                    name: item.filename,
                    filename: item.filename,
                    title: item.title,
                    artist: item.artist,
                    album: item.album,
                    albumartist: item.albumartist || item.artist,
                    tracknumber: item.tracknumber,
                    discnumber: item.discnumber,
                    genre: item.genre,
                    album_img: item.album_img
                }))

                // 先标记为 wait 状态
                selectedItems.forEach(item => {
                    this.$set(this.batchStatusMap, item.filename, { state: 'wait', extra: '' })
                })

                this.isAiSubmitting = true
                this.$api.Task.batchUpdateId3({
                    file_full_path: this.filePath,
                    select_data: selectData,
                    apply_to_all: false,
                    music_info: {}
                }).then(res => {
                    if (res && res.result) {
                        const batchId = res.data ? res.data.batch : ''
                        this.startBatchStatusPolling(batchId)
                        this.$cwMessage(`智能规划任务已成功提交至任务中心（共 ${selectData.length} 首），正在后台并发执行`, 'success')
                        this.planReviewDialogVisible = false
                    } else {
                        this.$cwMessage('批量修改提交失败: ' + (res ? res.message : ''), 'error')
                        selectedItems.forEach(item => {
                            this.$delete(this.batchStatusMap, item.filename)
                        })
                    }
                }).catch(err => {
                    this.$cwMessage('批量修改提交异常: ' + err, 'error')
                    selectedItems.forEach(item => {
                        this.$delete(this.batchStatusMap, item.filename)
                    })
                }).finally(() => {
                    this.isAiSubmitting = false
                })
            },
            // ==================== 提示词模板管理 ====================
            openPromptManager() {
                if (!this.promptTemplates || this.promptTemplates.length === 0) {
                    this.resetPromptDefaults(false)
                }
                const activeId = this.aiPlanForm.templateId
                const activeTpl = this.promptTemplates.find(t => t.id === activeId) || this.promptTemplates[0]
                this.selectPromptToEdit(activeTpl)
                this.promptManagerVisible = true
            },
            selectPromptToEdit(tpl) {
                if (!tpl) return
                this.editingPrompt = JSON.parse(JSON.stringify(tpl))
            },
            addNewPrompt() {
                const newTpl = {
                    id: 'tpl_custom_' + Date.now(),
                    name: '新建规划模板',
                    mode: this.aiPlanForm.mode || 'course',
                    isDefault: false,
                    isBuiltin: false,
                    systemPrompt: '你是一个音频标签整理专家。',
                    userPrompt: '当前处理目录：{dir_name}\n请针对以下音频文件列表，规划其标准元数据：\n{files}'
                }
                this.promptTemplates.push(newTpl)
                this.selectPromptToEdit(newTpl)
            },
            saveEditingPrompt() {
                if (!this.editingPrompt || !this.editingPrompt.name.trim()) {
                    this.$cwMessage('模板名称不能为空', 'warning')
                    return
                }

                // 如果设为了该模式下的默认，先将该模式下其他模板取消默认
                if (this.editingPrompt.isDefault) {
                    this.promptTemplates.forEach(t => {
                        if (t.mode === this.editingPrompt.mode && t.id !== this.editingPrompt.id) {
                            t.isDefault = false
                        }
                    })
                }

                const idx = this.promptTemplates.findIndex(t => t.id === this.editingPrompt.id)
                if (idx !== -1) {
                    this.$set(this.promptTemplates, idx, JSON.parse(JSON.stringify(this.editingPrompt)))
                } else {
                    this.promptTemplates.push(JSON.parse(JSON.stringify(this.editingPrompt)))
                }

                try {
                    localStorage.setItem('mtw_prompt_templates', JSON.stringify(this.promptTemplates))
                } catch (e) {}

                // 同步当前表单提示词
                if (this.aiPlanForm.templateId === this.editingPrompt.id) {
                    this.aiPlanForm.systemPrompt = this.editingPrompt.systemPrompt || ''
                    this.aiPlanForm.userPrompt = this.editingPrompt.userPrompt || ''
                }

                this.$cwMessage('模板保存成功', 'success')
            },
            deleteCurrentPrompt() {
                if (!this.editingPrompt) return
                if (this.editingPrompt.isBuiltin) {
                    this.$cwMessage('系统内置模板不可删除', 'warning')
                    return
                }
                const delId = this.editingPrompt.id
                this.promptTemplates = this.promptTemplates.filter(t => t.id !== delId)
                try {
                    localStorage.setItem('mtw_prompt_templates', JSON.stringify(this.promptTemplates))
                } catch (e) {}
                this.$cwMessage('模板已删除', 'success')
                if (this.promptTemplates.length > 0) {
                    this.selectPromptToEdit(this.promptTemplates[0])
                }
            },
            // ==================== AI 模型配置 ====================
            openAiSettings() {
                this.aiTestStatus = {
                    tested: false,
                    success: false,
                    message: '',
                    latency: 0,
                    reply: ''
                }
                this.aiSettingsVisible = true
            },
            testAiConnection() {
                if (!this.aiConfig.model || !this.aiConfig.model.trim()) {
                    this.$cwMessage('请先输入模型名称 (Model Name)', 'warning')
                    return
                }
                this.isTestingAiConnection = true
                this.aiTestStatus = {
                    tested: false,
                    success: false,
                    message: '',
                    latency: 0,
                    reply: ''
                }
                this.$api.Task.agentTestConnection({
                    base_url: this.aiConfig.baseUrl,
                    api_key: this.aiConfig.apiKey,
                    model: this.aiConfig.model,
                    temperature: this.aiConfig.temperature
                }).then(res => {
                    if (res && res.result) {
                        const data = res.data || {}
                        this.aiTestStatus = {
                            tested: true,
                            success: true,
                            message: res.message || '连接成功，模型响应正常',
                            latency: data.latency_ms || 0,
                            reply: data.reply || ''
                        }
                        this.$cwMessage(this.aiTestStatus.message, 'success')
                    } else {
                        const errMsg = (res ? res.message : '连接测试失败')
                        this.aiTestStatus = {
                            tested: true,
                            success: false,
                            message: errMsg,
                            latency: 0,
                            reply: ''
                        }
                        this.$cwMessage('测试未通过: ' + errMsg, 'error')
                    }
                }).catch(err => {
                    const errMsg = '请求异常: ' + (err.message || err)
                    this.aiTestStatus = {
                        tested: true,
                        success: false,
                        message: errMsg,
                        latency: 0,
                        reply: ''
                    }
                    this.$cwMessage('测试请求异常', 'error')
                }).finally(() => {
                    this.isTestingAiConnection = false
                })
            },
            saveAiConfig() {
                try {
                    localStorage.setItem('mtw_ai_config', JSON.stringify(this.aiConfig))
                } catch (e) {}
                this.$cwMessage('模型配置已成功保存至本地', 'success')
                this.aiSettingsVisible = false
            },
            clearAiConfig() {
                this.aiConfig = {
                    apiKey: '',
                    baseUrl: 'https://api.openai.com/v1',
                    model: '',
                    temperature: 0.2
                }
                this.aiTestStatus = {
                    tested: false,
                    success: false,
                    message: '',
                    latency: 0,
                    reply: ''
                }
                try {
                    localStorage.removeItem('mtw_ai_config')
                } catch (e) {}
                this.$cwMessage('已清空大模型配置，将使用纯本地极速规则引擎', 'primary')
                this.aiSettingsVisible = false
            },
            // ==================== 课程封面智能制作与生成方法 ====================
            openCourseCoverDialog() {
                if (!this.filePath) {
                    this.$cwMessage('请先在左侧选择要制作封面的课程文件夹', 'warning')
                    return
                }

                const currentPath = (this.filePath || '').replace(/\\/g, '/').replace(/\/+$/, '')
                const parts = currentPath.split('/')
                const dirName = parts[parts.length - 1] || ''

                let suggestedTitle = ''
                let suggestedAuthor = ''
                let suggestedCategory = '得到课程'
                let suggestedStyle = 'amber_dark'

                // 1. 优先统计当前音频列表中的 album 与 artist 标签
                const albumVotes = {}
                const artistVotes = {}
                if (this.folderMusicList && this.folderMusicList.length > 0) {
                    for (const item of this.folderMusicList) {
                        const alb = (item.album || '').trim()
                        if (alb && !alb.includes('未知') && alb !== '未知专辑') {
                            albumVotes[alb] = (albumVotes[alb] || 0) + 1
                        }
                        const art = (item.artist || item.albumartist || '').trim()
                        if (art && !art.includes('未知') && art !== '未知歌手' && art !== '未知艺术家') {
                            artistVotes[art] = (artistVotes[art] || 0) + 1
                        }
                    }
                }

                const sortedAlbums = Object.keys(albumVotes).sort((a, b) => albumVotes[b] - albumVotes[a])
                if (sortedAlbums.length > 0) {
                    suggestedTitle = sortedAlbums[0]
                }

                const sortedArtists = Object.keys(artistVotes).sort((a, b) => artistVotes[b] - artistVotes[a])
                if (sortedArtists.length > 0) {
                    suggestedAuthor = sortedArtists[0]
                }

                // 2. 如果标签缺失，从目录名智能解析（如 "267 冯雪·女性健康管理60讲"、"01.吴军·科技史纲60讲"）
                if (!suggestedTitle || !suggestedAuthor) {
                    const cleanDir = dirName.replace(/^(\d+[\.\-_ ]+|\[[^\]]+\]|【[^】]+】)/g, '').trim()

                    if (cleanDir.includes('·')) {
                        const subs = cleanDir.split('·')
                        if (!suggestedAuthor) suggestedAuthor = subs[0].trim()
                        if (!suggestedTitle) suggestedTitle = subs.slice(1).join('·').trim()
                    } else if (cleanDir.includes('-')) {
                        const subs = cleanDir.split('-')
                        if (!suggestedTitle) suggestedTitle = subs[0].trim()
                        if (!suggestedAuthor) suggestedAuthor = subs[1].trim()
                    } else if (cleanDir.includes('_')) {
                        const subs = cleanDir.split('_')
                        if (!suggestedTitle) suggestedTitle = subs[0].trim()
                        if (!suggestedAuthor) suggestedAuthor = subs.slice(1).join('_').trim()
                    } else if (!suggestedTitle) {
                        suggestedTitle = cleanDir
                    }
                }

                // 清除标题残余前导数字或标签
                suggestedTitle = suggestedTitle.replace(/^(\d+[\.\-_ ]+|\[[^\]]+\]|【[^】]+】)/g, '').trim()
                if (!suggestedTitle) {
                    suggestedTitle = dirName || '得到课程'
                }

                // 3. 智能推断顶部徽章分类
                const fullText = (currentPath + ' ' + suggestedTitle + ' ' + suggestedAuthor).toLowerCase()
                if (fullText.includes('大师') || fullText.includes('60讲') || fullText.includes('30讲')) {
                    suggestedCategory = '得到大师课'
                } else if (fullText.includes('通识')) {
                    suggestedCategory = '得到通识课'
                } else if (fullText.includes('精品') || fullText.includes('特辑')) {
                    suggestedCategory = '得到精品课'
                } else if (fullText.includes('专栏')) {
                    suggestedCategory = '得到专栏'
                } else if (fullText.includes('得到')) {
                    suggestedCategory = '得到课程'
                } else {
                    suggestedCategory = '精品音频课'
                }

                // 4. 根据课程领域智能匹配专属提示词与配色
                let suggestedPrompt = ''
                if (fullText.includes('硅谷') || fullText.includes('来信') || fullText.includes('芯片') || fullText.includes('代码') || fullText.includes('算法') || fullText.includes('编程')) {
                    suggestedStyle = 'deep_blue'
                    suggestedPrompt = 'dark navy electronic PCB circuit board background, glowing cyan neon and brushed gold copper conductive tracks, motherboard microchips, a minimalist outline envelope icon made of circuit lines at top center, clean empty dark negative space in the center, radial dark vignette, sleek modern tech graphic design, vector aesthetic, 8k, masterpiece, no text'
                } else if (fullText.includes('健康') || fullText.includes('医学') || fullText.includes('女性') || fullText.includes('生命') || fullText.includes('心理') || fullText.includes('医疗') || fullText.includes('身体')) {
                    suggestedStyle = 'emerald'
                    suggestedPrompt = `modern health and medical science illustration for '${suggestedTitle}', serene healing aesthetic, soft eucalyptus green and warm rose quartz gradient, clean minimalist cellular and organic geometry, elegant soft studio lighting, 3d smooth clay render, 8k masterpiece`
                } else if (fullText.includes('经济') || fullText.includes('商业') || fullText.includes('管理') || fullText.includes('金融') || fullText.includes('财富') || fullText.includes('投资') || fullText.includes('创业')) {
                    suggestedStyle = 'amber_dark'
                    suggestedPrompt = `minimalist modern financial economics book cover background for '${suggestedTitle}', subtle geometric gradient, deep navy and warm gold accent, 3d smooth matte texture, studio lighting, masterpiece, 8k`
                } else if (fullText.includes('科技') || fullText.includes('ai') || fullText.includes('科学') || fullText.includes('技术') || fullText.includes('计算机') || fullText.includes('宇宙') || fullText.includes('物理') || fullText.includes('数学')) {
                    suggestedStyle = 'deep_blue'
                    suggestedPrompt = `deep dark universe tech exploration aesthetic for '${suggestedTitle}', subtle starlight glow, clean minimalist sphere and orbital curves, premium black gold tone, 8k`
                } else if (fullText.includes('历史') || fullText.includes('政治') || fullText.includes('战争') || fullText.includes('帝国') || fullText.includes('文明')) {
                    suggestedStyle = 'crimson'
                    suggestedPrompt = `magnificent epic historical civilization book cover illustration for '${suggestedTitle}', minimalist architectural geometry, warm terracotta red and antique gold gradient, dramatic cinematic studio lighting, 8k`
                } else if (fullText.includes('哲学') || fullText.includes('艺术') || fullText.includes('音乐') || fullText.includes('文学') || fullText.includes('美学')) {
                    suggestedStyle = 'purple'
                    suggestedPrompt = `minimalist abstract humanities art and philosophy book cover background for '${suggestedTitle}', elegant lavender purple and warm amber gradient, clean sculptural curves, contemplative lighting, 8k`
                } else {
                    suggestedStyle = 'amber_dark'
                    suggestedPrompt = `minimalist abstract modern knowledge course cover background for '${suggestedTitle}', geometric gradient, warm amber and clean beige tone, 3d smooth clay texture, studio lighting, masterpiece, 8k`
                }

                this.coverForm.title = suggestedTitle
                this.coverForm.author = suggestedAuthor
                this.coverForm.category = suggestedCategory
                this.coverForm.style = suggestedStyle
                this.coverForm.prompt = suggestedPrompt
                this.coverForm.layout = 'dedao_clean'
                this.coverForm.comfyui_url = localStorage.getItem('mtw_comfyui_url') || 'http://host.docker.internal:8188'
                this.courseCoverDialogVisible = true
            },
            setCoverPreset(preset) {
                const title = this.coverForm.title || '课程'
                const presets = {
                    '科技电路': 'dark navy electronic PCB circuit board background, glowing cyan neon and brushed gold copper conductive tracks, motherboard microchips, a minimalist outline envelope icon made of circuit lines at top center, clean empty dark negative space in the center, radial dark vignette, sleek modern tech graphic design, vector aesthetic, 8k, masterpiece, no text',
                    '极简商务': `minimalist abstract modern book cover background for '${title}', subtle geometric gradient, deep navy and warm gold accent, 3d smooth matte texture, studio lighting, masterpiece, 8k`,
                    '暖色几何': `minimalist abstract geometry illustration for '${title}', warm terracotta amber and beige gradient, clean architectural composition, soft shadows, 8k`,
                    '深邃探索': `deep dark universe exploration aesthetic for '${title}', subtle starlight glow, clean minimalist sphere and orbital curves, premium black gold tone, 8k`,
                    '自然治愈': `fresh organic minimalist background for '${title}', soft sage green and eucalyptus tones, clean sunlight diffusion, tranquil aesthetics, 8k`
                }
                this.coverForm.prompt = presets[preset] || presets['极简商务']
                if (preset === '科技电路') {
                    this.coverForm.layout = 'dedao_clean'
                }
            },
            handleTestComfyui() {
                const url = (this.coverForm.comfyui_url || '').trim()
                if (!url) {
                    this.$cwMessage('请填写 ComfyUI 服务地址', 'warning')
                    return
                }
                this.isTestingComfyui = true
                this.comfyuiTestResult = null
                this.$api.Task.testComfyuiConnection({ comfyui_url: url }).then(res => {
                    this.isTestingComfyui = false
                    if (res.result) {
                        this.comfyuiTestResult = { success: true, msg: '✅ ' + res.message }
                        this.$cwMessage(res.message, 'success')
                        try {
                            localStorage.setItem('mtw_comfyui_url', url)
                        } catch (e) {}
                    } else {
                        this.comfyuiTestResult = { success: false, msg: '❌ ' + (res.message || '测试失败') }
                        this.$cwMessage('连接失败: ' + (res.message || '未知错误'), 'error')
                    }
                }).catch(err => {
                    this.isTestingComfyui = false
                    this.comfyuiTestResult = { success: false, msg: '❌ 网络异常: ' + (err.message || err) }
                    this.$cwMessage('连接异常: ' + (err.message || err), 'error')
                })
            },
            handleGenerateCover() {
                if (!this.coverForm.title.trim()) {
                    this.$cwMessage('请填写课程主标题', 'warning')
                    return
                }
                if (!this.filePath) {
                    this.$cwMessage('未检测到当前课程目录路径', 'warning')
                    return
                }

                try {
                    localStorage.setItem('mtw_comfyui_url', this.coverForm.comfyui_url)
                } catch (e) {}

                this.isGeneratingCover = true
                this.generateCostSeconds = 0
                if (this.generateTimer) {
                    clearInterval(this.generateTimer)
                }
                this.generateTimer = setInterval(() => {
                    this.generateCostSeconds++
                }, 1000)

                this.$api.Task.generateCourseCover({
                    folder_path: this.filePath,
                    title: this.coverForm.title.trim(),
                    author: this.coverForm.author.trim(),
                    category: this.coverForm.category.trim() || '得到课程',
                    prompt: this.coverForm.prompt.trim(),
                    engine: this.coverForm.engine,
                    quality: this.coverForm.quality || 'fast',
                    layout: this.coverForm.layout || 'dedao_clean',
                    font_size: this.coverForm.font_size || 'auto',
                    comfyui_url: this.coverForm.comfyui_url.trim(),
                    style: this.coverForm.style
                }).then(res => {
                    if (res.result) {
                        this.generatedCoverBase64 = res.data.image_base64
                        let sourceLabel = '极速几何美学引擎'
                        if (res.data.source === 'comfyui_moss_image') {
                            sourceLabel = 'ComfyUI (MOSS-Image)'
                        } else if (res.data.source && res.data.source.includes('fallback')) {
                            sourceLabel = '几何美学 (ComfyUI超时降级)'
                            this.$cwMessage('ComfyUI 响应过慢，已自动呈现几何美学专属封面', 'warning')
                        }
                        this.generatedCoverMeta = {
                            source: sourceLabel,
                            cost_sec: res.data.cost_sec,
                            title: res.data.title,
                            author: res.data.author
                        }
                        this.$cwMessage('新封面已成功绘制并取回！', 'success')
                    } else {
                        this.$cwMessage('生成失败: ' + (res.message || '未知错误'), 'error')
                    }
                }).catch(err => {
                    this.$cwMessage('生成异常: ' + (err.message || err), 'error')
                }).finally(() => {
                    if (this.generateTimer) {
                        clearInterval(this.generateTimer)
                        this.generateTimer = null
                    }
                    this.isGeneratingCover = false
                })
            },
            handleApplyCover() {
                if (!this.generatedCoverBase64) {
                    this.$cwMessage('请先生成封面预览', 'warning')
                    return
                }
                this.isSavingCover = true
                this.$api.Task.applyCourseCover({
                    folder_path: this.filePath,
                    image_base64: this.generatedCoverBase64,
                    embed_to_files: this.coverForm.embed_to_files
                }).then(res => {
                    if (res.result) {
                        this.$cwMessage(res.message || '封面已成功应用！', 'success')
                        this.courseCoverDialogVisible = false
                        this.fetchFolderMusicList()
                    } else {
                        this.$cwMessage('应用失败: ' + (res.message || '未知错误'), 'error')
                    }
                }).catch(err => {
                    this.$cwMessage('应用异常: ' + (err.message || err), 'error')
                }).finally(() => {
                    this.isSavingCover = false
                })
            }
        }
    }
</script>
<style lang="postcss">
.bk-table-header .custom-header-cell {
    color: inherit;
    text-decoration: underline;
    text-decoration-style: dashed;
    text-underline-position: under;
}

.music-item {
    cursor: pointer;
}

.music-item:hover {
    color: #1facdd;
}

.label1 {
    width: 80px;
}

.parent {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    grid-template-rows: repeat(1, 1fr);
    grid-column-gap: 0;
    grid-row-gap: 0;
    place-items: center;
    margin-bottom: 15px;
}

.title2 {
    font-weight: 500;
}

.song-card {
    display: flex;
    align-items: center;
    border-bottom: 1px solid #E2E2E2;
}

.song-card:hover {
    background: #E2E2E2;
}

.add-button {
    width: 24px;
    height: 24px;
    line-height: 20px;
    display: inline-block;
    background-color: transparent;
    border: 1px solid #ccc;
    border-radius: 5px;
    margin-left: 5px;
    font-size: 12px;
    color: rgb(97, 97, 97);
    text-align: center;
    cursor: pointer;
}

.delete-button {
    width: 24px;
    height: 24px;
    line-height: 20px;
    display: inline-block;
    background-color: transparent;
    border: 1px solid #ccc;
    border-radius: 5px;
    margin-left: 5px;
    font-size: 12px;
    color: rgb(63, 63, 63);
    text-align: center;
    cursor: pointer;
}

/* 全局布局与顶部导航 */
.home-main-layout {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #f5f7fa;
}

.top-nav-bar {
    height: 48px;
    min-height: 48px;
    flex-shrink: 0;
    background: #ffffff;
    border-bottom: 1px solid #dcdee5;
    display: flex;
    align-items: center;
    padding: 0 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    z-index: 10;
}

.top-nav-left {
    display: flex;
    align-items: center;
    margin-right: 14px;
    border-right: 1px solid #dcdee5;
    padding-right: 10px;
}

.nav-act-btn {
    margin-right: 6px;
    font-size: 13px;
    color: #63656e;
}
.nav-act-btn:hover {
    color: #3a84ff;
}

.top-nav-center {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    margin-right: 14px;
}

.path-breadcrumb-wrap {
    display: flex;
    align-items: center;
    width: 100%;
    background: #f0f1f5;
    border-radius: 4px;
    padding: 3px 8px;
    border: 1px solid #dcdee5;
}

.path-breadcrumb {
    display: flex;
    align-items: center;
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    white-space: nowrap;
    font-size: 13px;
    color: #495060;
    flex: 1;
}

.path-breadcrumb::-webkit-scrollbar {
    height: 3px;
}
.path-breadcrumb::-webkit-scrollbar-thumb {
    background: #c4c6cc;
    border-radius: 2px;
}

.path-segment {
    cursor: pointer;
    padding: 1px 6px;
    border-radius: 3px;
    color: #495060;
    transition: all 0.2s;
    user-select: none;
}
.path-segment:hover {
    background: #e1ecff;
    color: #3a84ff;
}
.root-segment {
    font-weight: 500;
    color: #3a84ff;
    display: inline-flex;
    align-items: center;
}
.path-separator {
    color: #979ba5;
    margin: 0 3px;
    user-select: none;
}

.edit-path-btn {
    cursor: pointer;
    margin-left: 8px;
    color: #979ba5;
    padding: 2px 4px;
    border-radius: 3px;
    display: inline-flex;
    align-items: center;
}
.edit-path-btn:hover {
    color: #3a84ff;
    background: #e1ecff;
}

.path-input-wrap {
    display: flex;
    align-items: center;
    width: 100%;
}

.top-nav-right {
    display: flex;
    align-items: center;
}

.history-dropdown-list {
    max-height: 280px;
    overflow-y: auto;
}
.history-item a {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 320px;
    font-size: 12px;
}
.clear-history-item a {
    color: #ea3636 !important;
    text-align: center;
    border-top: 1px solid #f0f1f5;
}

.main-workspace {
    flex: 1;
    height: 0;
    min-height: 0;
    display: flex;
    overflow: hidden;
    padding: 10px;
    box-sizing: border-box;
}

.resource-section {
    flex: 1;
    min-width: 0;
    height: 100%;
    background: #ffffff;
    border: 1px solid #dcdee5;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: all 0.25s ease;
}

.song-edit-drawer {
    width: 480px;
    min-width: 480px;
    height: 100%;
    background: #ffffff;
    border: 1px solid #dcdee5;
    border-radius: 6px;
    margin-left: 10px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.06);
}

.drawer-header {
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    border-bottom: 1px solid #dcdee5;
    background: #fafbfd;
}

.drawer-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
}

.drawer-slide-enter-active, .drawer-slide-leave-active {
    transition: all 0.25s ease;
}
.drawer-slide-enter, .drawer-slide-leave-to {
    transform: translateX(30px);
    opacity: 0;
}

.resource-header {
    flex-shrink: 0;
    border-bottom: 1px solid #eef0f5;
    background: #ffffff;
}

.file-list-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 44px;
    padding: 0 16px;
}

.subview-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 44px;
    padding: 0 16px;
    background: #f8fafc;
}

.size-btn {
    cursor: pointer;
    font-weight: 700;
    margin-right: 12px;
    color: #495060;
    transition: all 0.2s;
    user-select: none;
    line-height: 1;
}

.size-btn.size-small {
    font-size: 13px;
}

.size-btn.size-medium {
    font-size: 15px;
}

.size-btn.size-large {
    font-size: 18px;
}

.size-btn.active-size {
    color: #7c6cf0 !important;
}

.toolbar-label {
    font-size: 13px;
    color: #63656e;
    margin-left: 12px;
    margin-right: 6px;
}

.page-size-select {
    height: 26px;
    padding: 0 6px;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    background: #ffffff;
    font-size: 12px;
    color: #63656e;
    outline: none;
    cursor: pointer;
}

.page-size-select:focus {
    border-color: #7c6cf0;
}

.total-count-text {
    font-size: 13px;
    color: #979ba5;
    user-select: none;
}

.table-container {
    flex: 1;
    height: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
}

.table-body-wrap {
    flex: 1;
    height: 0;
    min-height: 0;
    position: relative;
    overflow: hidden;
}

.table-cover-box {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    vertical-align: middle;
}

.table-cover-box.cover-small {
    width: 28px;
    height: 28px;
}

.table-cover-box.cover-medium {
    width: 36px;
    height: 36px;
}

.table-cover-box.cover-large {
    width: 46px;
    height: 46px;
}

.table-cover-img {
    width: 100%;
    height: 100%;
    border-radius: 4px;
    object-fit: cover;
    display: block;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

.table-cover-placeholder {
    width: 100%;
    height: 100%;
    border-radius: 4px;
    background: #e6e8ee;
    display: block;
}

.pill-badge {
    display: inline-block;
    padding: 0 8px;
    height: 18px;
    line-height: 16px;
    border-radius: 10px;
    font-size: 11px;
    border: 1px solid #b8aeff;
    color: #8c7af8;
    background: transparent;
    user-select: none;
    text-align: center;
    box-sizing: border-box;
}

.pill-badge.pill-badge-has {
    border-color: #7c6cf0;
    color: #7c6cf0;
    font-weight: 600;
}

.active-table-row {
    background-color: #ecf3fe !important;
}

.table-pagination-wrap {
    flex-shrink: 0;
    padding: 8px 16px;
    border-top: 1px solid #dfe0e5;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    background: #ffffff;
}

.bk-table-body-wrapper::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

.bk-table-body-wrapper::-webkit-scrollbar-thumb {
    background-color: #c4c6cc;
    border-radius: 3px;
}

.bk-table-body-wrapper::-webkit-scrollbar-thumb:hover {
    background-color: #979ba5;
}

.bk-table-body-wrapper::-webkit-scrollbar-track {
    background: transparent;
}

.bk-form-checkbox {
    margin-right: 10px;
}

.success {
    color: #d1cfc5;
}

.failed {
    color: #ac354b;
}

.null {
    color: #333146;
}

button.bk-success {
    background-color: rgb(17, 64, 108) !important;
    border-color: rgb(17, 64, 108) !important;
}

button.bk-primary {
    background-color: rgb(17, 64, 108) !important;
    border-color: rgb(17, 64, 108) !important;
}

button.bk-button-text {
    background-color: transparent !important;
}

.bk-form-checkbox.is-checked .bk-checkbox {
    border-color: rgb(17, 64, 108) !important;
    background-color: rgb(17, 64, 108) !important;
    background-clip: border-box !important;
}

.bk-button-group .bk-button.is-selected {
    border-color: rgb(17, 64, 108) !important;
    color: rgb(17, 64, 108) !important;
}

.bk-button.bk-default:hover {
    border-color: rgb(17, 64, 108) !important;
    color: rgb(17, 64, 108) !important;
}

.bk-form-radio input[type=radio].is-checked {
    color: rgb(17, 64, 108) !important;
}

.bk-steps .bk-step.current .bk-step-icon, .bk-steps .bk-step.current .bk-step-number, .bk-steps .bk-step.current .bk-step-text {
    border-color: rgb(17, 64, 108) !important;
    background-color: rgb(17, 64, 108) !important;
}

.bk-steps .bk-step.done .bk-step-icon, .bk-steps .bk-step.done .bk-step-number, .bk-steps .bk-step.done .bk-step-text {
    border-color: rgb(17, 64, 108) !important;
    color: rgb(17, 64, 108) !important;
}

.bk-icon.icon-arrows-left-circle {
    color: rgb(17, 64, 108) !important;
}

.bk-icon.icon-arrows-right-circle {
    color: rgb(17, 64, 108) !important;
}

.bk-icon.icon-arrows-right-shape {
    color: rgb(17, 64, 108) !important;
}

.bk-icon.icon-arrows-right-shape:hover {
    color: #df4d40 !important;
}

.bk-icon.icon-arrows-left-shape:hover {
    color: #df4d40 !important;
}

.bk-icon.icon-arrows-down-shape:hover {
    color: #df4d40 !important;
}

::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-thumb {
    background-color: #c4c6cc;
    border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
    background-color: #979ba5;
}

::-webkit-scrollbar-track {
    background-color: transparent;
}

.isSelected {
    background-color: #ecf3fe;
}

.edit-item {
    display: flex;
    margin-bottom: 10px;
    align-items: center;
}

.can-copy {
    cursor: pointer;
}

/* 批量修改与表头操作样式 */
.custom-table-header-cell {
    display: inline-flex;
    align-items: center;
    position: relative;
}

.header-batch-icon {
    margin-left: 5px;
    font-size: 13px;
    color: #979ba5;
    cursor: pointer;
    padding: 2px;
    border-radius: 3px;
    transition: all 0.2s;
}

.header-batch-icon:hover {
    color: #3a84ff;
    background: #e1ecff;
    transform: scale(1.15);
}

.batch-status-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 1px 7px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 500;
    line-height: 18px;
}

.batch-status-badge i {
    margin-right: 3px;
    font-size: 12px;
}

.status-none {
    background: #f0f1f5;
    color: #979ba5;
    border: 1px solid #dcdee5;
}

.status-wait {
    background: #fff4e5;
    color: #ff9c01;
    border: 1px solid #ffd699;
}

.status-running {
    background: #e1ecff;
    color: #3a84ff;
    border: 1px solid #a3c5fd;
}

.status-success {
    background: #e4faf0;
    color: #10c17a;
    border: 1px solid #85e8ba;
}

.status-failed {
    background: #ffebeb;
    color: #ea3636;
    border: 1px solid #fd9c9c;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.spin-icon {
    display: inline-block;
    animation: spin 1s linear infinite;
}

.batch-modal-body {
    padding: 4px 0;
}

.batch-scope-bar {
    display: flex;
    align-items: center;
    background: #f5f7fa;
    padding: 8px 14px;
    border-radius: 4px;
    margin-bottom: 12px;
}

.scope-label {
    font-size: 13px;
    font-weight: bold;
    color: #313238;
    margin-right: 12px;
}

.scope-tip {
    margin-left: 14px;
    font-size: 12px;
    color: #979ba5;
}

.batch-field-pills-wrap {
    margin-bottom: 12px;
}

.pills-title {
    font-size: 13px;
    font-weight: bold;
    color: #313238;
    display: block;
    margin-bottom: 8px;
}

.batch-field-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.field-pill-item {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
}

.field-pill-item:hover {
    border-color: #3a84ff;
}

.field-pill-item.pill-active {
    border-color: #3a84ff;
    background: #f0f5ff;
    box-shadow: 0 0 0 1px #3a84ff;
}

.field-pill-item .pill-name {
    margin-left: 6px;
    font-size: 13px;
    color: #63656e;
}

.field-pill-item.pill-active .pill-name {
    color: #3a84ff;
    font-weight: 500;
}

.pill-badge-check {
    margin-left: 6px;
    font-size: 10px;
    background: #3a84ff;
    color: #fff;
    padding: 0 4px;
    border-radius: 2px;
    line-height: 14px;
}

.batch-config-panel {
    border: 1px solid #dcdee5;
    border-radius: 4px;
    padding: 14px 16px;
    background: #fafbfd;
    margin-bottom: 14px;
}

.preset-row {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}

.preset-label {
    font-size: 12px;
    color: #63656e;
    font-weight: bold;
    width: 90px;
    flex-shrink: 0;
}

.preset-btns {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.template-input-row {
    margin-bottom: 12px;
}

.input-head {
    margin-bottom: 6px;
}

.input-title {
    font-size: 12px;
    font-weight: bold;
    color: #313238;
}

.var-tags-row {
    display: flex;
    align-items: flex-start;
    margin-top: 8px;
}

.var-tag-label {
    font-size: 12px;
    color: #979ba5;
    margin-right: 6px;
    white-space: nowrap;
    line-height: 22px;
}

.var-tags-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.var-tag-btn {
    display: inline-block;
    font-size: 11px;
    color: #3a84ff;
    background: #e1ecff;
    padding: 2px 7px;
    border-radius: 3px;
    cursor: pointer;
    border: 1px solid #c5daff;
    transition: all 0.15s;
    user-select: none;
}

.var-tag-btn:hover {
    background: #3a84ff;
    color: #fff;
}

.trim-config-box {
    border-top: 1px dashed #dcdee5;
    padding-top: 10px;
    margin-top: 6px;
}

.trim-box-title {
    font-size: 12px;
    font-weight: bold;
    color: #63656e;
    margin-bottom: 8px;
}

.trim-box-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
}

.trim-field-group {
    display: flex;
    align-items: center;
    font-size: 12px;
    color: #63656e;
}

.trim-field-label {
    font-weight: bold;
    margin-right: 4px;
}

.sub-label {
    margin: 0 4px;
}

.batch-preview-container {
    margin-top: 12px;
}

.preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
}

.preview-title {
    font-size: 13px;
    font-weight: bold;
    color: #313238;
}

.preview-table-wrap {
    max-height: 160px;
    overflow-y: auto;
    border: 1px solid #dcdee5;
    border-radius: 4px;
}

.batch-preview-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    table-layout: fixed;
}

.batch-preview-table th, .batch-preview-table td {
    border: 1px solid #f0f1f5;
    padding: 6px 10px;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.batch-preview-table th {
    background: #f5f7fa;
    color: #63656e;
    font-weight: bold;
}

.filename-cell {
    color: #313238;
    font-weight: 500;
}

.preview-cover-cell {
    display: flex;
    align-items: center;
    gap: 8px;
}

.cover-thumb-box {
    width: 28px;
    height: 28px;
    border-radius: 2px;
    overflow: hidden;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #dcdee5;
    background: #fff;
}

.thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.thumb-none, .thumb-clear, .thumb-keep {
    font-size: 10px;
    color: #979ba5;
}

.thumb-clear {
    color: #ea3636;
    font-weight: bold;
}

.preview-text-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    overflow: hidden;
}

.diff-old {
    color: #979ba5;
    max-width: 45%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.diff-arrow {
    color: #3a84ff;
    font-weight: bold;
    flex-shrink: 0;
}

.diff-new {
    color: #10c17a;
    font-weight: 500;
    max-width: 45%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.batch-dialog-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 10px 0 0 0;
}

.footer-left-info {
    font-size: 13px;
    color: #63656e;
}

.footer-left-info strong {
    color: #3a84ff;
    font-size: 15px;
}

/* 顶部导航徽章与按钮样式 */
.task-badge-pill {
    margin-left: 5px;
    padding: 0 6px;
    font-size: 11px;
    height: 16px;
    line-height: 16px;
    border-radius: 8px;
    display: inline-block;
    font-weight: 600;
}
.task-badge-pill.pill-failed {
    background: #ea3636;
    color: #ffffff;
}
.task-badge-pill.pill-total {
    background: #e1ecff;
    color: #3a84ff;
}
.nav-act-btn.force-refresh-btn:hover {
    background: #fff4e5;
}

/* 任务列表弹窗内容样式 */
.task-panel-wrap {
    padding: 10px 0;
}
.task-stats-cards {
    display: flex;
    gap: 12px;
    margin-bottom: 14px;
}
.stat-card {
    flex: 1;
    background: #f5f7fa;
    border: 1px solid #dcdee5;
    border-radius: 6px;
    padding: 10px 14px;
    cursor: pointer;
    transition: all 0.2s ease;
}
.stat-card:hover {
    border-color: #3a84ff;
    background: #ffffff;
    box-shadow: 0 2px 8px rgba(58, 132, 255, 0.12);
}
.stat-card.stat-active {
    border-color: #3a84ff;
    background: #f0f5ff;
}
.stat-card .stat-num {
    font-size: 20px;
    font-weight: 700;
    color: #313238;
}
.stat-card .stat-label {
    font-size: 12px;
    color: #63656e;
    margin-top: 2px;
}
.stat-card.stat-failed .stat-num {
    color: #ea3636;
}
.stat-card.stat-running .stat-num {
    color: #3a84ff;
}
.stat-card.stat-success .stat-num {
    color: #2dcb56;
}
.task-panel-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 4px;
}
.task-panel-toolbar .toolbar-left,
.task-panel-toolbar .toolbar-right {
    display: flex;
    align-items: center;
}
.task-type-tag {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
}
.task-type-tag.type-manual {
    background: #e1ecff;
    color: #3a84ff;
}
.task-type-tag.type-auto {
    background: #f2eafd;
    color: #7c42f0;
}
.task-type-tag.type-tidy {
    background: #e5f6ea;
    color: #2dcb56;
}
.tidy-dialog-content {
    padding: 6px 4px 10px 4px;
}
.tidy-form-label {
    font-size: 13px;
    font-weight: 500;
    color: #313238;
    margin-bottom: 6px;
}
.tidy-tip {
    font-size: 12px;
    color: #979ba5;
    margin-top: 4px;
}
.task-pagination-wrap {
    margin-top: 12px;
    display: flex;
    justify-content: flex-end;
}

/* ==================== AI 智能规划 Agent 样式 ==================== */
.ai-plan-dialog-body {
    padding: 10px 6px;
}
.ai-plan-target-banner {
    display: flex;
    align-items: center;
    background: #f0f5ff;
    border: 1px solid #c3d7ff;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 13px;
    margin-bottom: 16px;
}
.ai-plan-target-banner .target-title {
    color: #3a84ff;
    font-weight: 600;
    white-space: nowrap;
}
.ai-plan-target-banner .target-path {
    color: #313238;
    font-family: monospace;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 460px;
}
.ai-plan-target-banner .target-count {
    color: #63656e;
    margin-left: 8px;
    white-space: nowrap;
}
.ai-section {
    margin-bottom: 14px;
}
.ai-section-title {
    font-size: 13px;
    font-weight: 600;
    color: #313238;
    margin-bottom: 8px;
}
.ai-mode-cards {
    display: flex;
    gap: 12px;
}
.ai-mode-card {
    flex: 1;
    border: 1px solid #dcdee5;
    border-radius: 6px;
    padding: 12px;
    background: #fff;
    cursor: pointer;
    transition: all .2s;
    position: relative;
}
.ai-mode-card:hover {
    border-color: #3a84ff;
    box-shadow: 0 2px 8px rgba(58, 132, 255, 0.12);
}
.ai-mode-card.mode-active {
    border-color: #3a84ff;
    background: #f0f5ff;
    box-shadow: 0 0 0 1px #3a84ff;
}
.ai-mode-card .mode-header {
    display: flex;
    align-items: center;
    margin-bottom: 6px;
}
.ai-mode-card .mode-icon {
    font-size: 16px;
    margin-right: 6px;
}
.ai-mode-card .mode-name {
    font-size: 13px;
    font-weight: 600;
    color: #313238;
}
.ai-mode-card .mode-badge {
    margin-left: auto;
    font-size: 11px;
    color: #fff;
    background: #3a84ff;
    padding: 1px 6px;
    border-radius: 10px;
}
.ai-mode-card .mode-desc {
    font-size: 12px;
    color: #63656e;
    line-height: 1.5;
}
.ai-template-select {
    width: 100%;
    height: 32px;
    line-height: 30px;
    padding: 0 8px;
    font-size: 12px;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    background: #fff;
    color: #313238;
    outline: none;
}
.ai-template-select:focus {
    border-color: #3a84ff;
}
.ai-custom-prompt-wrap {
    margin-top: 10px;
    background: #fafbfd;
    border: 1px dashed #c4c6cc;
    border-radius: 4px;
    padding: 10px 12px;
}
.ai-prompt-textarea {
    width: 100%;
    padding: 8px;
    font-size: 12px;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    resize: vertical;
    box-sizing: border-box;
    outline: none;
    font-family: inherit;
}
.ai-prompt-textarea:focus {
    border-color: #3a84ff;
}
.ai-engine-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 18px;
    padding: 10px 14px;
    background: #fafbfd;
    border: 1px solid #e1e3e8;
    border-radius: 4px;
}
.ai-engine-banner .engine-info {
    display: flex;
    align-items: center;
    font-size: 12px;
}
.ai-engine-banner .engine-status {
    font-weight: 600;
    margin-right: 6px;
}
.ai-engine-banner .engine-local {
    color: #2dcb56;
}
.ai-engine-banner .engine-llm {
    color: #ff9c00;
}
.ai-engine-banner .engine-model-tag {
    background: #ffe8c3;
    color: #cf7900;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-family: monospace;
    margin-right: 6px;
}
.ai-engine-banner .engine-tip {
    color: #979ba5;
    font-size: 11px;
}
.ai-engine-banner .engine-config-link {
    font-size: 12px;
    color: #3a84ff;
    text-decoration: none;
}
.ai-engine-banner .engine-config-link:hover {
    text-decoration: underline;
}

/* 规划结果审查与差异确认样式 */
.plan-review-body {
    padding: 4px 0;
}
.plan-summary-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f5f7fa;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    padding: 8px 14px;
    margin-bottom: 10px;
}
.plan-summary-bar .summary-left {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
}
.plan-summary-bar .summary-meta-item {
    font-size: 12px;
    display: flex;
    align-items: center;
}
.plan-summary-bar .meta-label {
    color: #63656e;
}
.plan-summary-bar .meta-val {
    color: #313238;
    font-weight: 600;
    max-width: 320px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.plan-summary-bar .meta-val.highlight {
    color: #3a84ff;
}
.plan-summary-bar .meta-sub {
    color: #63656e;
    margin-left: 4px;
}
.plan-summary-bar .meta-badge.badge-cover {
    background: #e5f6ea;
    color: #2dcb56;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 500;
}
.plan-summary-bar .summary-stat-pill {
    font-size: 12px;
    background: #e1ecff;
    color: #3a84ff;
    padding: 3px 10px;
    border-radius: 12px;
}
.plan-toolbar-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 2px;
}
.plan-toolbar-bar .plan-tools-left {
    display: flex;
    align-items: center;
}
.plan-toolbar-bar .toolbar-sep {
    color: #dcdee5;
    margin: 0 12px;
}
.plan-toolbar-bar .filter-label {
    font-size: 12px;
    color: #63656e;
    margin-right: 8px;
}
.plan-table-wrap {
    max-height: 480px;
    overflow-y: auto;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    margin-top: 8px;
    background: #fff;
}
.plan-diff-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}
.plan-diff-table th {
    position: sticky;
    top: 0;
    z-index: 2;
    background: #fafbfd;
    color: #63656e;
    font-weight: 600;
    padding: 8px 10px;
    border-bottom: 1px solid #dcdee5;
    border-right: 1px solid #f0f1f5;
    text-align: left;
}
.plan-diff-table td {
    padding: 6px 8px;
    border-bottom: 1px solid #f0f1f5;
    border-right: 1px solid #f5f6fa;
    vertical-align: middle;
}
.plan-diff-table tr.row-unselected {
    opacity: 0.55;
    background: #fbfbfc;
}
.plan-diff-table tr.row-edited {
    background: #fffef0;
}
.plan-cell-input {
    width: 100%;
    height: 28px;
    line-height: 26px;
    padding: 0 8px;
    font-size: 12px;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    background: #fff;
    box-sizing: border-box;
    transition: border-color .2s;
}
.plan-cell-input:focus {
    border-color: #3a84ff;
    outline: none;
    box-shadow: 0 0 0 2px rgba(58, 132, 255, 0.15);
}
.plan-track-input {
    text-align: center;
    font-weight: 600;
    color: #3a84ff;
    font-family: monospace;
}
.plan-title-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.plan-title-input {
    font-weight: 500;
}
.plan-orig-hint {
    font-size: 11px;
    color: #ea3636;
    background: #fdeeee;
    padding: 1px 4px;
    border-radius: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.plan-file-hint {
    font-size: 11px;
    color: #979ba5;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.badge-cover-yes {
    display: inline-block;
    font-size: 11px;
    background: #e5f6ea;
    color: #2dcb56;
    padding: 1px 6px;
    border-radius: 4px;
    font-family: monospace;
}
.badge-cover-none {
    color: #c4c6cc;
    font-size: 11px;
}
.plan-cleanups-wrap {
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.conf-badge-row {
    display: flex;
    align-items: center;
}
.conf-tag {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 600;
}
.conf-tag.conf-high {
    background: #e5f6ea;
    color: #2dcb56;
}
.conf-tag.conf-med {
    background: #fff3e1;
    color: #ff9c00;
}
.conf-tag.conf-low {
    background: #fee;
    color: #ea3636;
}
.cleanup-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
}
.cleanup-pill {
    font-size: 10px;
    background: #f0f1f5;
    color: #63656e;
    padding: 1px 5px;
    border-radius: 3px;
}
.plan-reason-text {
    font-size: 11px;
    color: #979ba5;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.plan-review-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
}
.plan-review-footer .review-footer-left {
    font-size: 13px;
    color: #63656e;
}
.plan-review-footer .review-footer-left strong {
    color: #3a84ff;
    font-size: 15px;
}

/* 提示词模板管理样式 */
.prompt-manager-body {
    display: flex;
    gap: 16px;
    height: 480px;
}
.pm-left-col {
    width: 250px;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    background: #fafbfd;
}
.pm-list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    border-bottom: 1px solid #dcdee5;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
}
.pm-list-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 6px;
}
.pm-tpl-item {
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 4px;
    margin-bottom: 6px;
    cursor: pointer;
    background: #fff;
    transition: all .15s;
}
.pm-tpl-item:hover {
    border-color: #c4c6cc;
}
.pm-tpl-item.tpl-active {
    border-color: #3a84ff;
    background: #e1ecff;
}
.pm-item-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}
.pm-tpl-name {
    font-size: 12px;
    font-weight: 600;
    color: #313238;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.pm-mode-tag {
    font-size: 10px;
    padding: 1px 4px;
    border-radius: 3px;
}
.pm-mode-tag.course {
    background: #e1ecff;
    color: #3a84ff;
}
.pm-mode-tag.music {
    background: #f2eafd;
    color: #7c42f0;
}
.pm-item-bottom {
    display: flex;
    gap: 6px;
    font-size: 10px;
}
.pm-default-badge {
    color: #ff9c00;
    font-weight: 600;
}
.pm-builtin-badge {
    color: #979ba5;
}
.pm-custom-badge {
    color: #2dcb56;
}
.pm-list-footer {
    padding: 8px;
    border-top: 1px solid #dcdee5;
}
.pm-right-col {
    flex: 1;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    padding: 14px;
    background: #fff;
    display: flex;
    flex-direction: column;
}
.pm-form-row {
    margin-bottom: 12px;
}
.pm-label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: #313238;
    margin-bottom: 6px;
}
.pm-textarea {
    width: 100%;
    padding: 8px;
    font-size: 12px;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    font-family: inherit;
    box-sizing: border-box;
    outline: none;
    resize: vertical;
}
.pm-textarea:focus {
    border-color: #3a84ff;
}
.pm-actions-bar {
    margin-top: auto;
    display: flex;
    align-items: center;
    padding-top: 10px;
    border-top: 1px solid #f0f1f5;
}

/* AI 设置样式 */
.ai-settings-body {
    padding: 6px 4px;
}
.ai-settings-notice {
    display: flex;
    align-items: flex-start;
    background: #f0f5ff;
    border: 1px solid #c3d7ff;
    border-radius: 4px;
    padding: 10px 12px;
    font-size: 12px;
    color: #313238;
    line-height: 1.5;
    margin-bottom: 16px;
}
.ai-setting-row {
    margin-bottom: 14px;
}
.ai-setting-label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: #313238;
    margin-bottom: 6px;
}
.ai-setting-tip {
    font-size: 11px;
    color: #979ba5;
    margin-top: 4px;
}
.ai-setting-tip code {
    background: #f0f1f5;
    padding: 1px 4px;
    border-radius: 2px;
    color: #3a84ff;
}

/* 连通性测试结果面板样式 */
.ai-test-result-box {
    margin-top: 14px;
    padding: 10px 14px;
    border-radius: 4px;
    font-size: 12px;
    line-height: 1.5;
    transition: all .2s;
}
.ai-test-result-box.test-success {
    background: #f2fff4;
    border: 1px solid #94ebaf;
    color: #1a7a37;
}
.ai-test-result-box.test-failed {
    background: #fff3f3;
    border: 1px solid #fecaca;
    color: #b91c1c;
}
.ai-test-result-box .result-header {
    display: flex;
    align-items: center;
    font-weight: 600;
    margin-bottom: 4px;
}
.ai-test-result-box .result-latency {
    margin-left: auto;
    font-family: monospace;
    font-size: 11px;
    background: rgba(0, 0, 0, 0.05);
    padding: 1px 6px;
    border-radius: 4px;
}
.ai-test-result-box .result-message {
    margin-bottom: 4px;
    word-break: break-all;
}
.ai-test-result-box .result-reply {
    font-size: 11px;
    color: #555;
    margin-top: 4px;
    word-break: break-all;
}
.ai-test-result-box .result-reply code {
    background: rgba(0, 0, 0, 0.06);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: monospace;
}

/* 课程专属封面弹窗样式 */
.course-cover-dialog-body {
    display: flex;
    gap: 20px;
    min-height: 480px;
    padding: 10px 0;
}
.cover-left-pane {
    flex: 1.15;
    display: flex;
    flex-direction: column;
}
.cover-right-pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: #f8fafc;
    border-radius: 8px;
    padding: 16px;
    border: 1px dashed #cbd5e1;
}
.cover-preview-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
}
.cover-img-box {
    position: relative;
    width: 320px;
    height: 320px;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
    border: 2px solid #fff;
    background: #1e293b;
}
.cover-loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(4px);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 10;
    text-align: center;
    padding: 20px;
}
@keyframes coverSpin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
.spin-icon {
    animation: coverSpin 1s linear infinite;
    display: inline-block;
}
.cover-img-box img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}
.cover-empty-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 320px;
    width: 100%;
}
.cover-meta-bar {
    margin-top: 14px;
    font-size: 12px;
    color: #475569;
    background: #fff;
    padding: 6px 14px;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.cover-dialog-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
}
.preset-pills {
    display: flex;
    gap: 8px;
    margin-bottom: 6px;
}
.pill-tag {
    font-size: 11px;
    padding: 2px 8px;
    background: #e2e8f0;
    color: #334155;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
}
.pill-tag:hover {
    background: #3a84ff;
    color: #fff;
}
.form-group-row {
    display: flex;
    width: 100%;
}
.form-group-item {
    display: flex;
    flex-direction: column;
    margin-bottom: 10px;
}
.form-label {
    font-size: 12px;
    font-weight: bold;
    color: #334155;
    margin-bottom: 4px;
}
.bk-form-textarea {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
    resize: vertical;
    outline: none;
    font-family: inherit;
}
.bk-form-textarea:focus {
    border-color: #3a84ff;
}
.bk-form-select {
    height: 32px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0 8px;
    font-size: 12px;
    outline: none;
    background: #fff;
}
.bk-form-select:focus {
    border-color: #3a84ff;
}
</style>
