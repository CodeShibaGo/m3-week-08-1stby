// 替換成你自己的 API 金鑰
const API_KEY = 'AIzaSyAK2QmcY4B563bRHCFl05gxbYRl2h-RBHw';

// 搜索函數
function search() {
    // 獲取搜索關鍵字
    const query = $('#query').val();

    // 發送 Axios 請求
    axios.get('https://www.googleapis.com/youtube/v3/search', {
        params: {
            part: 'snippet',
            maxResults: 5, // 指定最大返回結果
            q: query, // 搜索關鍵字
            key: API_KEY, // API 金鑰
            type: 'video' // 只搜索影片
        }
    })
        .then(function (response) {
            // 清空之前的搜索結果
            $('#results').empty();



            // 遍歷搜索結果
            response.data.items.forEach(item => {
                const videoId = item.id.videoId;
                const title = item.snippet.title;
                const description = item.snippet.description;
                const thumbnail = item.snippet.thumbnails.default.url;

                // 創建搜索結果項目
                const resultItem = `
                    <li class="list-item">
                        <div class="list-left">
                            <img src="${thumbnail}" alt="${title}">
                        </div>
                        <div class="list-right">
                            <a class="fancybox fancybox.iframe" href="https://www.youtube.com/embed/${videoId}" data-fancybox-type="iframe">
                                <h3>${title}</h3>
                            </a>
                            <p>${description}</p>
                        </div>
                    </li>
                `;

                // 添加到搜索結果列表
                $('#results').append(resultItem);
            });

        })
        .catch(function (error) {
            alert('Failed to load search results');
            console.log(error);
        });
}

// 綁定搜索表單提交事件
$('#search-form').submit(function (e) {
    e.preventDefault(); // 防止表單提交導致頁面重載
    search(); // 執行搜索函數
});